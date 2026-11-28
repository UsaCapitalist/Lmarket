"""
مرحله‌ی 5f: رکورد ساختاریافته‌ی برداشت در log (برای اعتبارسنجی). هیچ قاعده‌ی مالی عوض نمی‌شود
(تست‌های 3a/3b آن را می‌سنجند). مبلغ‌ها با موجودی قابل‌خرج بازیگران فیکسچر هماهنگ‌اند:
آلیس (سازنده) حدود ۷٫۵ ALGO، باب حدود ۹٫۹ ALGO.
"""
import config
import helpers
import records
from helpers import ALGO

DAY = 86_400
AGREED = 5 * ALGO


def active_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ فعال‌شده، هنوز قفل‌نشده."""
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def test_one_record_with_fixed_length_and_old_event_still_present(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 3 * ALGO)
    logs = helpers.withdraw_logs(app, bob, 1 * ALGO)
    recs = [x for x in logs if x.startswith(records.WITHDRAW_PREFIX)]
    assert len(recs) == 1 and len(recs[0]) == records.WITHDRAW_LEN == 52
    assert b"EVENT:withdrawn" in logs                             # log قبلی دست‌نخورده است


def test_buyer_record_fields_before_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, alice, 2 * ALGO)                         # واریزی طرف مقابل
    helpers.deposit(app, bob, 3 * ALGO)
    rec = records.withdraw_records(helpers.withdraw_logs(app, bob, 1 * ALGO))[0]
    s = helpers.read_state(app)
    assert rec["who"] == "B" and rec["amount"] == 1 * ALGO and rec["locked"] == 0
    assert rec["other_dep"] == s["seller_dep"] == 2 * ALGO
    assert rec["own_after"] == s["buyer_dep"] == 2 * ALGO
    assert rec["time"] >= s["activated_at"] > 0


def test_seller_record_fields_before_lock(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 4 * ALGO)
    helpers.deposit(app, alice, 3 * ALGO)
    rec = records.withdraw_records(helpers.withdraw_logs(app, alice, 2 * ALGO))[0]
    s = helpers.read_state(app)
    assert rec["who"] == "S" and rec["amount"] == 2 * ALGO and rec["locked"] == 0
    assert rec["other_dep"] == s["buyer_dep"] == 4 * ALGO
    assert rec["own_after"] == s["seller_dep"] == 1 * ALGO


def test_counterparty_without_deposit_is_recorded_as_zero(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 2 * ALGO)
    rec = records.withdraw_records(helpers.withdraw_logs(app, bob, 2 * ALGO))[0]
    assert rec["other_dep"] == 0 and rec["own_after"] == 0 and rec["locked"] == 0


def test_surplus_withdraw_after_lock_is_marked_locked(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED + 2 * ALGO)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    rec = records.withdraw_records(helpers.withdraw_logs(app, bob, 2 * ALGO))[0]
    assert rec["locked"] == 1 and rec["own_after"] == AGREED and rec["other_dep"] == AGREED


def test_each_withdraw_gets_its_own_record_with_decreasing_balance(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 4 * ALGO)
    after = []
    for _ in range(3):
        after.append(records.withdraw_records(helpers.withdraw_logs(app, bob, 1 * ALGO))[0]["own_after"])
    assert after == [3 * ALGO, 2 * ALGO, 1 * ALGO]


def test_withdraw_while_counterparty_is_ready_is_detectable(alice, bob):
    """الگوی معطل‌کردن: باب کامل واریز کرده، آلیس ناقص واریز می‌کند و بخشی را برمی‌دارد، پیش از قفل."""
    app = active_app(alice, bob)
    helpers.deposit(app, alice, 4 * ALGO)
    helpers.deposit(app, bob, AGREED)                             # طرف مقابل آماده است (به agreed رسیده)
    rec = records.withdraw_records(helpers.withdraw_logs(app, alice, 2 * ALGO))[0]
    assert rec["who"] == "S" and rec["locked"] == 0
    assert rec["other_dep"] >= AGREED                             # نشانه‌ی برداشت در حالی که طرف مقابل آماده بود
    assert rec["own_after"] == 2 * ALGO


def test_decoder_rejects_malformed_records():
    import pytest
    with pytest.raises(AssertionError):
        records.decode_withdraw(b"EVENT:withdrawn_v1" + b"\x00" * 33)     # یک بایت کم
    ok = records.decode_withdraw(b"EVENT:withdrawn_v1" + b"B" + b"\x00" * 33)   # شاهد: طول درست
    assert ok["who"] == "B" and ok["amount"] == 0
