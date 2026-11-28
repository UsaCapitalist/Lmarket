"""
مرحله‌ی 5a: ثبت کلید عمومی Ed25519 هر طرف (فقط ثبت؛ هنوز امضایی بررسی نمی‌شود).
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند حالت دست‌نخورده ماند.
کلید پیش از ثبت در حافظه وجود ندارد؛ read_state کلید ۳۲بایتی را به صورت آدرس برمی‌گرداند.
"""
from algosdk import account, encoding

import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_ACTIVE = "contract not activated"
R_PARTY = "only buyer or seller may register key"
R_LEN = "key must be 32 bytes"
R_TWICE = "key already registered"


def new_key() -> bytes:
    """یک کلید عمومی ۳۲بایتی تازه (مقدار دقیق مهم نیست؛ فقط ثبت می‌شود)."""
    _, addr = account.generate_account()
    return encoding.decode_address(addr)


def as_state(key: bytes) -> str:
    return encoding.encode_address(key)           # همان قالبی که read_state برمی‌گرداند


def new_app(alice, bob):
    """آلیس فروشنده و سازنده، باب خریدار؛ هنوز فعال نشده."""
    return helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)


def active_app(alice, bob):
    app = new_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    return app


def test_no_key_is_registered_initially(alice, bob):
    s = helpers.read_state(active_app(alice, bob))
    assert s["buyer_key_at"] == 0 and s["seller_key_at"] == 0
    assert "buyer_key" not in s and "seller_key" not in s


def test_buyer_registers_own_key_with_time(alice, bob):
    app = active_app(alice, bob)
    k = new_key()
    helpers.register_key(app, bob, k)
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(k)
    assert s["buyer_key_at"] >= s["activated_at"] > 0
    assert s["seller_key_at"] == 0 and "seller_key" not in s      # طرف دیگر دست‌نخورده


def test_seller_registers_own_key_with_time(alice, bob):
    app = active_app(alice, bob)
    k = new_key()
    helpers.register_key(app, alice, k)
    s = helpers.read_state(app)
    assert s["seller_key"] == as_state(k)
    assert s["seller_key_at"] >= s["activated_at"] > 0
    assert s["buyer_key_at"] == 0 and "buyer_key" not in s


def test_both_parties_register_independently(alice, bob):
    app = active_app(alice, bob)
    kb, ks = new_key(), new_key()
    helpers.register_key(app, bob, kb)
    helpers.register_key(app, alice, ks)                          # ثبت یک طرف مانع طرف دیگر نیست
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(kb) and s["seller_key"] == as_state(ks)


def test_cannot_register_before_activation(alice, bob):
    app = new_app(alice, bob)
    with rejected(R_ACTIVE):
        helpers.register_key(app, bob, new_key())
    assert helpers.read_state(app)["buyer_key_at"] == 0
    helpers.activate(app, alice, config.APP_FUND)                 # شاهد: پس از فعال‌سازی مجاز است
    helpers.register_key(app, bob, new_key())
    assert helpers.read_state(app)["buyer_key_at"] > 0


def test_outsider_cannot_register_key(alice, bob, mallory):
    app = active_app(alice, bob)
    with rejected(R_PARTY):
        helpers.register_key(app, mallory, new_key())
    s = helpers.read_state(app)
    assert s["buyer_key_at"] == 0 and s["seller_key_at"] == 0
    helpers.register_key(app, bob, new_key())                     # شاهد


def test_key_must_be_exactly_32_bytes(alice, bob):
    app = active_app(alice, bob)
    for bad in (b"", b"\x01" * 31, b"\x01" * 33):
        with rejected(R_LEN):
            helpers.register_key(app, bob, bad)
    assert helpers.read_state(app)["buyer_key_at"] == 0
    helpers.register_key(app, bob, b"\x01" * 32)                  # شاهد: دقیقاً ۳۲ بایت
    assert helpers.read_state(app)["buyer_key_at"] > 0


def test_key_cannot_be_registered_twice(alice, bob):
    app = active_app(alice, bob)
    first = new_key()
    helpers.register_key(app, bob, first)
    with rejected(R_TWICE):
        helpers.register_key(app, bob, new_key())
    s = helpers.read_state(app)
    assert s["buyer_key"] == as_state(first)                      # کلید اول دست‌نخورده
    helpers.register_key(app, alice, new_key())                   # شاهد: طرف دیگر هنوز می‌تواند


def test_register_key_moves_no_money_and_changes_no_other_state(alice, bob):
    app = active_app(alice, bob)
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.register_key(app, bob, new_key())
    after = helpers.read_state(app)
    assert helpers.balance(addr) == before_bal
    skip = ("buyer_key", "buyer_key_at")
    assert {k: v for k, v in after.items() if k not in skip} == {k: v for k, v in before.items() if k not in skip}


def test_register_key_works_after_lock_and_changes_no_rules(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    helpers.register_key(app, alice, new_key())                   # پس از قفل هم مجاز است
    with rejected("withdraw exceeds free balance"):
        helpers.withdraw(app, alice, 1)                           # قفل همچنان برقرار است
    assert helpers.read_state(app)["seller_dep"] == AGREED
