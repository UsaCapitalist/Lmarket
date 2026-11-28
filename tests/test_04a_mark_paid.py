"""
مرحله‌ی 4a: ثبت پرداخت (mark_paid) توسط خریدار.
این ثبت فقط اعلام است: نباید پولی جابه‌جا کند و نباید قواعد قفل و برداشت را تغییر دهد.
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند حالت دست‌نخورده ماند.
"""
import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_BUYER = "only buyer may mark paid"
R_LOCK = "mark paid requires lock"
R_TWICE = "already marked paid"
R_FREE = "withdraw exceeds free balance"


def active_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ agreed = ۵ ALGO؛ فعال‌شده، هنوز قفل‌نشده."""
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def locked_app(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    return app


def test_paid_is_zero_initially(alice, bob):
    assert helpers.read_state(active_app(alice, bob))["paid"] == 0
    assert helpers.read_state(locked_app(alice, bob))["paid"] == 0


def test_buyer_can_mark_paid_after_lock(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    assert helpers.read_state(app)["paid"] == 1


def test_mark_paid_moves_no_money_and_changes_no_other_state(alice, bob):
    app = locked_app(alice, bob)
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.mark_paid(app, bob)
    after = helpers.read_state(app)
    assert helpers.balance(addr) == before_bal
    assert {k: v for k, v in after.items() if k not in ("paid", "paid_at")} == {k: v for k, v in before.items() if k not in ("paid", "paid_at")}


def test_seller_cannot_mark_paid(alice, bob):
    app = locked_app(alice, bob)
    with rejected(R_BUYER):
        helpers.mark_paid(app, alice)                         # فروشنده نمی‌تواند پرداخت را ثبت کند
    assert helpers.read_state(app)["paid"] == 0
    helpers.mark_paid(app, bob)                               # شاهد: خریدار می‌تواند


def test_outsider_cannot_mark_paid(alice, bob, mallory):
    app = locked_app(alice, bob)
    with rejected(R_BUYER):
        helpers.mark_paid(app, mallory)
    assert helpers.read_state(app)["paid"] == 0
    helpers.mark_paid(app, bob)                               # شاهد


def test_cannot_mark_paid_before_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)                         # باب واریز کرده، آلیس نه: قفل نیست
    with rejected(R_LOCK):
        helpers.mark_paid(app, bob)
    assert helpers.read_state(app)["paid"] == 0
    helpers.deposit(app, alice, AGREED)                       # شاهد: پس از قفل مجاز می‌شود
    helpers.mark_paid(app, bob)
    assert helpers.read_state(app)["paid"] == 1


def test_cannot_mark_paid_twice(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    with rejected(R_TWICE):
        helpers.mark_paid(app, bob)
    assert helpers.read_state(app)["paid"] == 1


def test_mark_paid_does_not_release_locked_collateral(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)                         # وثیقه‌ی خریدار همچنان قفل است
    with rejected(R_FREE):
        helpers.withdraw(app, alice, 1)                       # وثیقه‌ی فروشنده هم
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * AGREED


def test_surplus_stays_withdrawable_after_mark_paid(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 7 * ALGO)                       # ۲ ALGO مازاد
    helpers.deposit(app, alice, AGREED)
    helpers.mark_paid(app, bob)
    helpers.withdraw(app, bob, 2 * ALGO)                      # مازاد آزاد است
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)
    assert helpers.read_state(app)["buyer_dep"] == AGREED


def test_deposit_still_works_after_mark_paid(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    helpers.deposit(app, alice, 1 * ALGO)
    assert helpers.read_state(app)["seller_dep"] == AGREED + 1 * ALGO
