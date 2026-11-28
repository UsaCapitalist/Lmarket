"""
مرحله‌ی 5e: ثبت طرفی که با واریزش قفل را کامل کرد (locked_by). فقط ثبت است؛ قواعد مالی تغییر نمی‌کند.
تا پیش از قفل، locked_by اصلاً در حافظه نیست.
هر رد‌شدن یا نبودن مقدار، شاهد موفق دارد.
"""
import config
import helpers
from helpers import ALGO

DAY = 86_400
AGREED = 5 * ALGO


def active_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ فعال‌شده، هنوز قفل‌نشده."""
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def test_locked_by_is_absent_before_lock(alice, bob):
    app = active_app(alice, bob)
    assert "locked_by" not in helpers.read_state(app)
    helpers.deposit(app, bob, AGREED)                             # فقط یک طرف
    assert "locked_by" not in helpers.read_state(app)
    helpers.deposit(app, alice, AGREED)                           # شاهد: با قفل ثبت می‌شود
    assert "locked_by" in helpers.read_state(app)


def test_second_depositor_is_the_locker_seller_last(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked_by"] == alice.address


def test_second_depositor_is_the_locker_buyer_last(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, AGREED)
    helpers.deposit(app, bob, AGREED)
    assert helpers.read_state(app)["locked_by"] == bob.address


def test_partial_deposits_the_completing_one_counts(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 2 * ALGO)                           # ناقص
    helpers.deposit(app, alice, AGREED)
    assert "locked_by" not in helpers.read_state(app)             # باب هنوز کامل نکرده
    helpers.deposit(app, bob, 3 * ALGO)                           # باب با این واریزی کامل می‌کند
    assert helpers.read_state(app)["locked_by"] == bob.address


def test_oversized_first_deposit_does_not_make_that_party_the_locker(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, 2 * AGREED)                       # آلیس اضافه واریز می‌کند ولی قفل نیست
    assert "locked_by" not in helpers.read_state(app)
    helpers.deposit(app, bob, AGREED)
    assert helpers.read_state(app)["locked_by"] == bob.address


def test_withdraw_before_lock_then_redeposit_changes_the_locker(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.withdraw(app, bob, AGREED)                            # باب پس می‌گیرد
    helpers.deposit(app, alice, AGREED)
    assert "locked_by" not in helpers.read_state(app)
    helpers.deposit(app, bob, AGREED)                             # باب دوباره واریز می‌کند و قفل را کامل می‌کند
    assert helpers.read_state(app)["locked_by"] == bob.address


def test_locked_by_never_changes_after_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    helpers.deposit(app, bob, 1 * ALGO)                           # واریزی‌های بعدی (مازاد) هر دو طرف
    helpers.deposit(app, alice, 1 * ALGO)
    helpers.withdraw(app, bob, 1 * ALGO)
    assert helpers.read_state(app)["locked_by"] == alice.address


def test_locked_by_is_one_of_the_parties_and_matches_the_lock_time_state(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    s = helpers.read_state(app)
    assert s["locked_by"] in (s["buyer"], s["seller"])
    assert s["locked"] == 1 and s["locked_at"] > 0
