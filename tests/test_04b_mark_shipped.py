"""
مرحله‌ی ۴ب: ثبت ارسال (mark_shipped) توسط فروشنده.
مثل mark_paid فقط اعلام است: نباید پولی جابه‌جا کند و نباید قواعد قفل و برداشت را تغییر دهد.
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند حالت دست‌نخورده ماند.
"""
import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_SELLER = "only seller may mark shipped"
R_LOCK = "mark shipped requires lock"
R_TWICE = "already marked shipped"
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


def test_shipped_is_zero_initially(alice, bob):
    assert helpers.read_state(active_app(alice, bob))["shipped"] == 0
    assert helpers.read_state(locked_app(alice, bob))["shipped"] == 0


def test_seller_can_mark_shipped_after_lock(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_shipped(app, alice)
    assert helpers.read_state(app)["shipped"] == 1


def test_mark_shipped_moves_no_money_and_changes_no_other_state(alice, bob):
    app = locked_app(alice, bob)
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.mark_shipped(app, alice)
    after = helpers.read_state(app)
    assert helpers.balance(addr) == before_bal
    assert {k: v for k, v in after.items() if k != "shipped"} == {k: v for k, v in before.items() if k != "shipped"}


def test_buyer_cannot_mark_shipped(alice, bob):
    app = locked_app(alice, bob)
    with rejected(R_SELLER):
        helpers.mark_shipped(app, bob)                        # خریدار نمی‌تواند ارسال را ثبت کند
    assert helpers.read_state(app)["shipped"] == 0
    helpers.mark_shipped(app, alice)                          # شاهد: فروشنده می‌تواند


def test_outsider_cannot_mark_shipped(alice, bob, mallory):
    app = locked_app(alice, bob)
    with rejected(R_SELLER):
        helpers.mark_shipped(app, mallory)
    assert helpers.read_state(app)["shipped"] == 0
    helpers.mark_shipped(app, alice)                          # شاهد


def test_cannot_mark_shipped_before_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, AGREED)                       # آلیس واریز کرده، باب نه: قفل نیست
    with rejected(R_LOCK):
        helpers.mark_shipped(app, alice)
    assert helpers.read_state(app)["shipped"] == 0
    helpers.deposit(app, bob, AGREED)                         # شاهد: پس از قفل مجاز می‌شود
    helpers.mark_shipped(app, alice)
    assert helpers.read_state(app)["shipped"] == 1


def test_cannot_mark_shipped_twice(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_shipped(app, alice)
    with rejected(R_TWICE):
        helpers.mark_shipped(app, alice)
    assert helpers.read_state(app)["shipped"] == 1


# ---------------------------------------------------------------- استقلال از mark_paid
def test_paid_then_shipped(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    helpers.mark_shipped(app, alice)
    s = helpers.read_state(app)
    assert (s["paid"], s["shipped"]) == (1, 1)


def test_shipped_then_paid(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_shipped(app, alice)
    s = helpers.read_state(app)
    assert (s["paid"], s["shipped"]) == (0, 1)                # ارسال، پرداخت را ثبت نمی‌کند
    helpers.mark_paid(app, bob)
    s = helpers.read_state(app)
    assert (s["paid"], s["shipped"]) == (1, 1)


def test_both_marks_do_not_release_locked_collateral(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_paid(app, bob)
    helpers.mark_shipped(app, alice)
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)
    with rejected(R_FREE):
        helpers.withdraw(app, alice, 1)
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * AGREED


def test_surplus_stays_withdrawable_after_mark_shipped(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, 7 * ALGO)                     # ۲ ALGO مازاد برای فروشنده
    helpers.deposit(app, bob, AGREED)
    helpers.mark_shipped(app, alice)
    helpers.withdraw(app, alice, 2 * ALGO)                    # مازاد آزاد است
    with rejected(R_FREE):
        helpers.withdraw(app, alice, 1)
    assert helpers.read_state(app)["seller_dep"] == AGREED
