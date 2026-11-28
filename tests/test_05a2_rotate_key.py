"""
مرحله‌ی 5a2: تعویض کلید عمومی Ed25519 (کلید قبلی منسوخ می‌شود).
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند حالت دست‌نخورده ماند.
read_state کلید ۳۲بایتی را به صورت آدرس برمی‌گرداند. شمارنده‌ی *_key_n پیش از تعویض اول ۰ است.
"""
from algosdk import account, encoding

import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_PARTY = "only buyer or seller may rotate key"
R_LEN = "key must be 32 bytes"
R_NOT_REG = "key not registered"
R_SAME = "new key must differ"


def new_key() -> bytes:
    _, addr = account.generate_account()
    return encoding.decode_address(addr)


def as_state(key: bytes) -> str:
    return encoding.encode_address(key)


def active_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ فعال‌شده."""
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def test_rotation_counter_is_zero_after_first_registration(alice, bob):
    app = active_app(alice, bob)
    s = helpers.read_state(app)
    assert s["buyer_key_n"] == 0 and s["seller_key_n"] == 0
    helpers.register_key(app, bob, new_key())
    assert helpers.read_state(app)["buyer_key_n"] == 0            # ثبت اول تعویض حساب نمی‌شود


def test_cannot_rotate_before_registration(alice, bob):
    app = active_app(alice, bob)
    with rejected(R_NOT_REG):
        helpers.rotate_key(app, bob, new_key())
    s = helpers.read_state(app)
    assert s["buyer_key_at"] == 0 and s["buyer_key_n"] == 0 and "buyer_key" not in s
    helpers.register_key(app, bob, new_key())                     # شاهد: پس از ثبت اول تعویض مجاز است
    helpers.rotate_key(app, bob, new_key())
    assert helpers.read_state(app)["buyer_key_n"] == 1


def test_buyer_rotation_replaces_key_and_counts(alice, bob):
    app = active_app(alice, bob)
    old, new = new_key(), new_key()
    helpers.register_key(app, bob, old)
    before = helpers.read_state(app)
    helpers.rotate_key(app, bob, new)
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(new) != as_state(old)
    assert s["buyer_key_at"] >= before["buyer_key_at"] > 0
    assert s["buyer_key_n"] == 1


def test_seller_rotation_replaces_key_and_counts(alice, bob):
    app = active_app(alice, bob)
    helpers.register_key(app, alice, new_key())
    new = new_key()
    helpers.rotate_key(app, alice, new)
    s = helpers.read_state(app)
    assert s["seller_key"] == as_state(new) and s["seller_key_n"] == 1
    assert s["buyer_key_n"] == 0


def test_rotation_can_repeat_and_counter_grows(alice, bob):
    app = active_app(alice, bob)
    helpers.register_key(app, bob, new_key())
    last = None
    for _ in range(3):
        last = new_key()
        helpers.rotate_key(app, bob, last)
    s = helpers.read_state(app)
    assert s["buyer_key_n"] == 3 and s["buyer_key"] == as_state(last)


def test_rotating_one_party_does_not_touch_the_other(alice, bob):
    app = active_app(alice, bob)
    ks = new_key()
    helpers.register_key(app, bob, new_key())
    helpers.register_key(app, alice, ks)
    helpers.rotate_key(app, bob, new_key())
    s = helpers.read_state(app)
    assert s["seller_key"] == as_state(ks) and s["seller_key_n"] == 0


def test_outsider_cannot_rotate_key(alice, bob, mallory):
    app = active_app(alice, bob)
    k = new_key()
    helpers.register_key(app, bob, k)
    with rejected(R_PARTY):
        helpers.rotate_key(app, mallory, new_key())
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(k) and s["buyer_key_n"] == 0
    helpers.rotate_key(app, bob, new_key())                       # شاهد


def test_rotated_key_must_be_exactly_32_bytes(alice, bob):
    app = active_app(alice, bob)
    k = new_key()
    helpers.register_key(app, bob, k)
    for bad in (b"", b"\x01" * 31, b"\x01" * 33):
        with rejected(R_LEN):
            helpers.rotate_key(app, bob, bad)
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(k) and s["buyer_key_n"] == 0
    helpers.rotate_key(app, bob, b"\x02" * 32)                    # شاهد


def test_new_key_must_differ_from_current(alice, bob):
    app = active_app(alice, bob)
    k = new_key()
    helpers.register_key(app, bob, k)
    with rejected(R_SAME):
        helpers.rotate_key(app, bob, k)
    assert helpers.read_state(app)["buyer_key_n"] == 0
    helpers.rotate_key(app, bob, new_key())                       # شاهد
    assert helpers.read_state(app)["buyer_key_n"] == 1


def test_rotate_key_moves_no_money_and_changes_no_other_state(alice, bob):
    app = active_app(alice, bob)
    helpers.register_key(app, bob, new_key())
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.rotate_key(app, bob, new_key())
    after = helpers.read_state(app)
    assert helpers.balance(addr) == before_bal
    skip = ("buyer_key", "buyer_key_at", "buyer_key_n")
    assert {k: v for k, v in after.items() if k not in skip} == {k: v for k, v in before.items() if k not in skip}


def test_rotate_key_works_after_lock_and_changes_no_rules(alice, bob):
    app = active_app(alice, bob)
    helpers.register_key(app, alice, new_key())
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    helpers.rotate_key(app, alice, new_key())                     # پس از قفل هم مجاز است
    with rejected("withdraw exceeds free balance"):
        helpers.withdraw(app, alice, 1)
    assert helpers.read_state(app)["locked"] == 1
