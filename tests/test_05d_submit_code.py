"""
مرحله‌ی 5d: ثبت کد تأیید توسط طرف مقابل (فقط زمان ثبت می‌شود؛ وجهی آزاد نمی‌شود).
نقش ۱ = کد فروشنده، توسط خریدار ثبت می‌شود؛ نقش ۲ = کد خریدار، توسط فروشنده ثبت می‌شود.
پس از ثبت کد، کلید امضاکننده قفل می‌شود (rotate_key رد می‌شود).
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد، یک شاهد موفق دارد، و ثابت می‌کند حالت دست‌نخورده ماند.
"""
from algosdk import encoding
from nacl.signing import SigningKey

import config
import helpers
import signing_message as sm
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_ROLE = "invalid role"
R_BUYER = "only buyer may submit seller code"
R_SELLER = "only seller may submit buyer code"
R_TWICE = "code already submitted"
R_LOCK = "message requires lock"
R_NO_KEY = "signer key not registered"
R_LEN = "signature must be 64 bytes"
R_SIG = "invalid signature"
R_FROZEN = "key frozen after code"


def keypair():
    sk = SigningKey.generate()
    return sk, bytes(sk.verify_key)


def sign(sk, msg: bytes) -> bytes:
    return sk.sign(msg).signature


def message_for(app, role):
    """پیام مرجع از روی حافظه‌ی قرارداد (با تابع خالص، مستقل از متد message)."""
    s = helpers.read_state(app)
    return sm.build_message(
        role, helpers.genesis_hash(), app,
        encoding.decode_address(s["buyer"]), encoding.decode_address(s["seller"]),
        s["agreed"], s["due_secs"], s["created_at"], s["activated_at"], s["locked_at"],
    )


def locked_app(alice, bob):
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    helpers.deposit(app, bob, AGREED)
    helpers.deposit(app, alice, AGREED)
    assert helpers.read_state(app)["locked"] == 1
    return app


def locked_app_with_keys(alice, bob):
    """آلیس فروشنده، باب خریدار؛ قفل‌شده و هر دو کلید ثبت‌شده."""
    app = locked_app(alice, bob)
    sk_b, pk_b = keypair()
    sk_s, pk_s = keypair()
    helpers.register_key(app, bob, pk_b)
    helpers.register_key(app, alice, pk_s)
    return app, sk_b, sk_s


def test_code_times_are_zero_initially(alice, bob):
    app, _, _ = locked_app_with_keys(alice, bob)
    s = helpers.read_state(app)
    assert s["seller_code_at"] == 0 and s["buyer_code_at"] == 0


def test_buyer_records_seller_code_and_seller_records_buyer_code(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))
    s = helpers.read_state(app)
    assert s["seller_code_at"] >= s["locked_at"] > 0
    assert s["buyer_code_at"] == 0                                # کد دیگر هنوز ثبت نشده
    helpers.submit_code(app, alice, 2, sign(sk_b, message_for(app, 2)))
    s = helpers.read_state(app)
    assert s["buyer_code_at"] >= s["locked_at"] > 0


def test_only_the_counterparty_may_submit(alice, bob, mallory):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    sig1, sig2 = sign(sk_s, message_for(app, 1)), sign(sk_b, message_for(app, 2))
    with rejected(R_BUYER):
        helpers.submit_code(app, alice, 1, sig1)                  # فروشنده کد خودش را نمی‌تواند ثبت کند
    with rejected(R_BUYER):
        helpers.submit_code(app, mallory, 1, sig1)
    with rejected(R_SELLER):
        helpers.submit_code(app, bob, 2, sig2)                    # خریدار کد خودش را نمی‌تواند ثبت کند
    with rejected(R_SELLER):
        helpers.submit_code(app, mallory, 2, sig2)
    s = helpers.read_state(app)
    assert s["seller_code_at"] == 0 and s["buyer_code_at"] == 0
    helpers.submit_code(app, bob, 1, sig1)                        # شاهد
    helpers.submit_code(app, alice, 2, sig2)


def test_invalid_signature_is_rejected_and_records_nothing(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    with rejected(R_SIG):
        helpers.submit_code(app, bob, 1, sign(sk_b, message_for(app, 1)))     # کلید طرف اشتباه
    with rejected(R_SIG):
        helpers.submit_code(app, bob, 1, sign(sk_s, b"hello"))                # پیام دیگر
    assert helpers.read_state(app)["seller_code_at"] == 0
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))         # شاهد


def test_each_code_can_be_recorded_only_once(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    good = sign(sk_s, message_for(app, 1))
    helpers.submit_code(app, bob, 1, good)
    first = helpers.read_state(app)["seller_code_at"]
    with rejected(R_TWICE):
        helpers.submit_code(app, bob, 1, good)                    # حتی با امضای درست
    assert helpers.read_state(app)["seller_code_at"] == first
    helpers.submit_code(app, alice, 2, sign(sk_b, message_for(app, 2)))       # شاهد: نقش دیگر هنوز آزاد است
    with rejected(R_TWICE):
        helpers.submit_code(app, alice, 2, sign(sk_b, message_for(app, 2)))


def test_invalid_role_is_rejected(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    for bad in (0, 3, 255):
        with rejected(R_ROLE):
            helpers.submit_code(app, bob, bad, b"\x01" * 64)
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))         # شاهد


def test_signature_length_and_key_registration_are_required(alice, bob):
    app = locked_app(alice, bob)
    with rejected(R_NO_KEY):
        helpers.submit_code(app, bob, 1, b"\x01" * 64)            # فروشنده کلید ثبت نکرده
    sk_s, pk_s = keypair()
    helpers.register_key(app, alice, pk_s)
    good = sign(sk_s, message_for(app, 1))
    for bad in (b"", good[:63], good + b"\x00"):
        with rejected(R_LEN):
            helpers.submit_code(app, bob, 1, bad)
    assert helpers.read_state(app)["seller_code_at"] == 0
    helpers.submit_code(app, bob, 1, good)                        # شاهد


def test_not_available_before_lock(alice, bob):
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    sk_s, pk_s = keypair()
    helpers.register_key(app, alice, pk_s)
    helpers.deposit(app, bob, AGREED)                             # فقط یک طرف: قفل نیست
    with rejected(R_LOCK):
        helpers.submit_code(app, bob, 1, b"\x01" * 64)
    assert helpers.read_state(app)["seller_code_at"] == 0
    helpers.deposit(app, alice, AGREED)                           # شاهد
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))


def test_code_from_another_contract_is_rejected():
    alice = helpers.new_actor("alice_rich", funded=40 * ALGO)
    bob = helpers.new_actor("bob_rich", funded=40 * ALGO)
    sk_s, pk_s = keypair()
    a, b = locked_app(alice, bob), locked_app(alice, bob)
    for app in (a, b):
        helpers.register_key(app, alice, pk_s)
    sig_a = sign(sk_s, message_for(a, 1))
    with rejected(R_SIG):
        helpers.submit_code(b, bob, 1, sig_a)                     # کد قرارداد الف در قرارداد ب بی‌اعتبار است
    assert helpers.read_state(b)["seller_code_at"] == 0
    helpers.submit_code(a, bob, 1, sig_a)                         # شاهد


def test_order_is_free_relative_to_declarations_and_nothing_is_released(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    addr = helpers.app_address(app)
    before_bal = helpers.balance(addr)
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))         # پیش از mark_paid و mark_shipped
    helpers.submit_code(app, alice, 2, sign(sk_b, message_for(app, 2)))
    helpers.mark_paid(app, bob)                                   # اعلام‌ها پس از کدها هم کار می‌کنند
    helpers.mark_shipped(app, alice)
    s = helpers.read_state(app)
    assert s["seller_code_at"] > 0 and s["buyer_code_at"] > 0 and s["paid"] == 1 and s["shipped"] == 1
    assert helpers.balance(addr) == before_bal                    # هیچ وجهی جابه‌جا نشد
    with rejected("withdraw exceeds free balance"):
        helpers.withdraw(app, bob, 1)                             # وثیقه‌ها هنوز قفل‌اند (تسویه در 6a)
    with rejected("withdraw exceeds free balance"):
        helpers.withdraw(app, alice, 1)


def test_submit_code_changes_no_other_state(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    before = helpers.read_state(app)
    helpers.submit_code(app, bob, 1, sign(sk_s, message_for(app, 1)))
    after = helpers.read_state(app)
    assert {k: v for k, v in after.items() if k != "seller_code_at"} == {k: v for k, v in before.items() if k != "seller_code_at"}


def test_signer_key_is_frozen_only_after_its_own_code_is_recorded(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    sk_new, pk_new = keypair()
    helpers.rotate_key(app, alice, pk_new)                        # پیش از ثبت کد، تعویض آزاد است (شاهد)
    helpers.submit_code(app, bob, 1, sign(sk_new, message_for(app, 1)))
    with rejected(R_FROZEN):
        helpers.rotate_key(app, alice, keypair()[1])              # کلید فروشنده پس از ثبت کدش قفل است
    assert helpers.read_state(app)["seller_key_n"] == 1           # فقط همان یک تعویض پیش از قفل
    sk_b2, pk_b2 = keypair()
    helpers.rotate_key(app, bob, pk_b2)                           # کلید خریدار هنوز قفل نیست
    helpers.submit_code(app, alice, 2, sign(sk_b2, message_for(app, 2)))
    with rejected(R_FROZEN):
        helpers.rotate_key(app, bob, keypair()[1])                # حالا کلید خریدار هم قفل شد
    assert helpers.read_state(app)["buyer_key_n"] == 1
