"""
مرحله‌ی 4c: ثبت زمان رویدادها (activated_at, locked_at, paid_at, shipped_at).
زمان‌ها فقط ثبت‌اند: پرچم‌های قبلی و قواعد مالی تغییر نمی‌کنند (تست‌های قبلی آن‌ها را می‌سنجند).
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند صفر ماند.
"""
import time

import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_ACT_AMOUNT = "activation payment must equal APP_FUND"
R_BUYER = "only buyer may mark paid"
R_SELLER = "only seller may mark shipped"

AT_KEYS = ("activated_at", "locked_at", "paid_at", "shipped_at")


def new_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ agreed = ۵ ALGO؛ هنوز فعال نشده."""
    return helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)


def locked_app(alice, bob):
    app = new_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    return app


def test_all_event_times_are_zero_after_create(alice, bob):
    s = helpers.read_state(new_app(alice, bob))
    assert s["created_at"] > 0                                # زمان ساخت از قبل ثبت می‌شد
    for k in AT_KEYS:
        assert s[k] == 0, k


def test_activate_records_time_and_only_that_time(alice, bob):
    app = new_app(alice, bob)
    with rejected(R_ACT_AMOUNT):
        helpers.activate(app, alice, config.APP_FUND - 1)     # فعال‌سازی ناموفق زمانی ثبت نمی‌کند
    assert helpers.read_state(app)["activated_at"] == 0
    helpers.activate(app, alice, config.APP_FUND)             # شاهد
    s = helpers.read_state(app)
    assert s["activated_at"] >= s["created_at"] > 0
    for k in ("locked_at", "paid_at", "shipped_at"):
        assert s[k] == 0, k


def test_lock_time_is_recorded_only_when_lock_happens(alice, bob):
    app = new_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    helpers.deposit(app, bob, AGREED)                         # فقط یک طرف: قفل نیست
    assert helpers.read_state(app)["locked_at"] == 0
    helpers.deposit(app, alice, AGREED)                       # شاهد: با واریز طرف دوم قفل می‌شود
    s = helpers.read_state(app)
    assert s["locked"] == 1
    assert s["locked_at"] >= s["activated_at"] > 0


def test_lock_time_does_not_change_after_later_deposits(alice, bob):
    app = locked_app(alice, bob)
    locked_at = helpers.read_state(app)["locked_at"]
    time.sleep(3)                                             # تا اگر بازنویسی شود، زمان فرق کند
    helpers.deposit(app, bob, 1 * ALGO)                       # واریز مازاد پس از قفل
    assert helpers.read_state(app)["locked_at"] == locked_at


def test_paid_time_is_recorded_for_buyer_only(alice, bob, mallory):
    app = locked_app(alice, bob)
    with rejected(R_BUYER):
        helpers.mark_paid(app, alice)
    with rejected(R_BUYER):
        helpers.mark_paid(app, mallory)
    assert helpers.read_state(app)["paid_at"] == 0            # ردشده‌ها زمانی ثبت نکردند
    helpers.mark_paid(app, bob)                               # شاهد
    s = helpers.read_state(app)
    assert s["paid_at"] >= s["locked_at"] > 0
    assert s["shipped_at"] == 0                               # زمان ارسال دست‌نخورده


def test_shipped_time_is_recorded_for_seller_only(alice, bob, mallory):
    app = locked_app(alice, bob)
    with rejected(R_SELLER):
        helpers.mark_shipped(app, bob)
    with rejected(R_SELLER):
        helpers.mark_shipped(app, mallory)
    assert helpers.read_state(app)["shipped_at"] == 0
    helpers.mark_shipped(app, alice)                          # شاهد
    s = helpers.read_state(app)
    assert s["shipped_at"] >= s["locked_at"] > 0
    assert s["paid_at"] == 0                                  # زمان پرداخت دست‌نخورده


def test_order_of_paid_and_shipped_is_free_and_times_are_consistent(alice, bob):
    app = locked_app(alice, bob)
    helpers.mark_shipped(app, alice)                          # ارسال پیش از پرداخت
    helpers.mark_paid(app, bob)
    s = helpers.read_state(app)
    assert s["created_at"] <= s["activated_at"] <= s["locked_at"] <= min(s["paid_at"], s["shipped_at"])
    assert s["paid_at"] > 0 and s["shipped_at"] > 0
