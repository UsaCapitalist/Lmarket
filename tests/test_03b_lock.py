"""
مرحله‌ی 3b: قفل دقیقِ مبلغ توافقی.
قاعده: با رسیدن واریزی هر دو طرف به agreed، دقیقاً agreed از هر طرف قفل می‌شود (نه کل واریزی)؛
مازاد آزاد و قابل برداشت می‌ماند. پیش از قفل هر طرف می‌تواند همه‌چیز را برگرداند.
"""
import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_FREE = "withdraw exceeds free balance"


def active_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ agreed = ۵ ALGO."""
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def test_not_locked_initially(alice, bob):
    app = active_app(alice, bob)
    assert helpers.read_state(app)["locked"] == 0


def test_one_side_reaching_agreed_does_not_lock_and_can_cancel(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    assert helpers.read_state(app)["locked"] == 0
    helpers.withdraw(app, bob, AGREED)                        # لغو کامل پیش از واریز طرف مقابل
    assert helpers.read_state(app)["buyer_dep"] == 0


def test_other_side_below_agreed_does_not_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED - 1)                   # یک میکروآلگو کم
    assert helpers.read_state(app)["locked"] == 0
    helpers.deposit(app, alice, 1)                            # شاهد: همان یک واحد، قفل می‌شود
    assert helpers.read_state(app)["locked"] == 1


def test_locks_when_both_reach_agreed_exactly(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    s = helpers.read_state(app)
    assert s["locked"] == 1
    assert (s["buyer_dep"], s["seller_dep"]) == (AGREED, AGREED)
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * AGREED


def test_lock_does_not_depend_on_order(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 0
    helpers.deposit(app, bob, AGREED)
    assert helpers.read_state(app)["locked"] == 1


def test_lock_reached_by_accumulating_deposits(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, AGREED)
    helpers.deposit(app, bob, 3 * ALGO)
    assert helpers.read_state(app)["locked"] == 0
    helpers.deposit(app, bob, 2 * ALGO)
    assert helpers.read_state(app)["locked"] == 1


def test_withdrawing_before_lock_delays_the_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.withdraw(app, bob, 1 * ALGO)                      # برداشت پیش از قفل مجاز است
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 0             # باب دیگر به agreed نرسیده
    helpers.deposit(app, bob, 1 * ALGO)
    assert helpers.read_state(app)["locked"] == 1


def test_locked_amount_cannot_be_withdrawn(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)                         # هیچ مازادی نیست
    with rejected(R_FREE):
        helpers.withdraw(app, alice, 1)
    assert helpers.read_state(app)["buyer_dep"] == AGREED


def test_only_the_surplus_is_withdrawable_after_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 7 * ALGO)                       # ۲ ALGO مازاد
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    helpers.withdraw(app, bob, 2 * ALGO)                      # شاهد: دقیقاً مازاد
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)
    s = helpers.read_state(app)
    assert s["buyer_dep"] == AGREED                           # دقیقاً agreed قفل مانده
    assert s["locked"] == 1


def test_surplus_over_limit_is_rejected_but_exact_surplus_passes(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 7 * ALGO)
    helpers.deposit(app, alice, AGREED)
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 2 * ALGO + 1)              # یک واحد بیش از مازاد
    helpers.withdraw(app, bob, 2 * ALGO)                      # شاهد


def test_deposit_after_lock_is_free_surplus(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    helpers.deposit(app, bob, 1 * ALGO)                       # واریز پس از قفل
    helpers.withdraw(app, bob, 1 * ALGO)                      # همان مازاد برمی‌گردد
    with rejected(R_FREE):
        helpers.withdraw(app, bob, 1)
    assert helpers.read_state(app)["buyer_dep"] == AGREED


def test_contract_holds_locked_funds_and_base_balance(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 7 * ALGO)
    helpers.deposit(app, alice, 6 * ALGO)
    helpers.withdraw(app, bob, 2 * ALGO)
    helpers.withdraw(app, alice, 1 * ALGO)
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * AGREED
