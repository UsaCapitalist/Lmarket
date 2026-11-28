"""
مرحله‌ی 5c: بررسی امضای کد تأیید با ed25519verify_bare (فقط می‌سنجد؛ چیزی ثبت نمی‌کند).
نقش ۱ = امضای فروشنده با کلید ثبت‌شده‌ی فروشنده، نقش ۲ = امضای خریدار با کلید ثبت‌شده‌ی خریدار.
پیامِ امضاشده از مرجع خالص tests/signing_message.py ساخته می‌شود (مستقل از قرارداد).
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد و یک شاهد موفق دارد.
"""
from algosdk import encoding
from nacl.signing import SigningKey

import config
import helpers
import signing_message as sm
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_LOCK = "message requires lock"
R_ROLE = "invalid role"
R_NO_KEY = "signer key not registered"
R_LEN = "signature must be 64 bytes"
R_SIG = "invalid signature"


def keypair():
    sk = SigningKey.generate()
    return sk, bytes(sk.verify_key)


def sign(sk, msg: bytes) -> bytes:
    return sk.sign(msg).signature                                 # امضای خام ۶۴بایتی Ed25519


def message_for(app, role):
    """پیام مرجع از روی حافظه‌ی قرارداد؛ با تابع خالص ساخته می‌شود، نه با متد message."""
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


def test_valid_seller_and_buyer_codes_pass(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    helpers.verify_code(app, bob, 1, sign(sk_s, message_for(app, 1)))     # فروشنده: نقش ۱
    helpers.verify_code(app, alice, 2, sign(sk_b, message_for(app, 2)))   # خریدار: نقش ۲


def test_signature_from_the_wrong_key_is_rejected(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, sign(sk_b, message_for(app, 1)))  # نقش ۱ را باید کلید فروشنده امضا کند
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 2, sign(sk_s, message_for(app, 2)))
    stranger, _ = keypair()
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, sign(stranger, message_for(app, 1)))   # کلید ثبت‌نشده
    helpers.verify_code(app, bob, 1, sign(sk_s, message_for(app, 1)))     # شاهد


def test_role_is_bound_even_when_both_parties_share_one_key(alice, bob):
    app = locked_app(alice, bob)
    sk, pk = keypair()
    helpers.register_key(app, bob, pk)
    helpers.register_key(app, alice, pk)                          # بدترین حالت: یک کلید برای هر دو نقش
    sig1 = sign(sk, message_for(app, 1))
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 2, sig1)                    # امضای نقش ۱ برای نقش ۲ پذیرفته نمی‌شود
    helpers.verify_code(app, bob, 1, sig1)                        # شاهد
    helpers.verify_code(app, bob, 2, sign(sk, message_for(app, 2)))


def test_code_from_another_contract_is_rejected():
    alice = helpers.new_actor("alice_rich", funded=40 * ALGO)
    bob = helpers.new_actor("bob_rich", funded=40 * ALGO)
    sk_s, pk_s = keypair()
    sk_b, pk_b = keypair()
    a, b = locked_app(alice, bob), locked_app(alice, bob)         # پارامترها و کلیدها یکی؛ فقط شناسه‌ی قرارداد فرق دارد
    for app in (a, b):
        helpers.register_key(app, alice, pk_s)
        helpers.register_key(app, bob, pk_b)
    sig_a = sign(sk_s, message_for(a, 1))
    with rejected(R_SIG):
        helpers.verify_code(b, bob, 1, sig_a)                     # کد قرارداد الف در قرارداد ب بی‌اعتبار است
    helpers.verify_code(a, bob, 1, sig_a)                         # شاهد: در خودش معتبر است
    helpers.verify_code(b, bob, 1, sign(sk_s, message_for(b, 1)))


def test_tampered_signature_and_wrong_message_are_rejected(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    good = sign(sk_s, message_for(app, 1))
    flipped = bytearray(good)
    flipped[0] ^= 1
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, bytes(flipped))          # یک بیت تغییر کرده
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, sign(sk_s, b"hello"))    # پیام دیگری امضا شده
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, sign(sk_s, message_for(app, 1)[:-1] + bytes([message_for(app, 1)[-1] ^ 1])))   # یک بیت از پیام فرق دارد
    helpers.verify_code(app, bob, 1, good)                        # شاهد


def test_signature_length_must_be_64_bytes(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    good = sign(sk_s, message_for(app, 1))
    for bad in (b"", good[:63], good + b"\x00"):
        with rejected(R_LEN):
            helpers.verify_code(app, bob, 1, bad)
    helpers.verify_code(app, bob, 1, good)                        # شاهد


def test_signer_key_must_be_registered(alice, bob):
    app = locked_app(alice, bob)
    sk_s, pk_s = keypair()
    with rejected(R_NO_KEY):
        helpers.verify_code(app, bob, 1, b"\x01" * 64)
    with rejected(R_NO_KEY):
        helpers.verify_code(app, bob, 2, b"\x01" * 64)
    helpers.register_key(app, alice, pk_s)                        # فقط فروشنده کلید ثبت می‌کند
    with rejected(R_NO_KEY):
        helpers.verify_code(app, bob, 2, b"\x01" * 64)            # نقش ۲ هنوز کلید ندارد
    helpers.verify_code(app, bob, 1, sign(sk_s, message_for(app, 1)))   # شاهد: نقش ۱ حالا قابل بررسی است


def test_not_available_before_lock(alice, bob):
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    sk_s, pk_s = keypair()
    helpers.register_key(app, alice, pk_s)
    helpers.deposit(app, bob, AGREED)                             # فقط یک طرف: قفل نیست
    with rejected(R_LOCK):
        helpers.verify_code(app, bob, 1, b"\x01" * 64)
    helpers.deposit(app, alice, AGREED)                           # شاهد: پس از قفل
    helpers.verify_code(app, bob, 1, sign(sk_s, message_for(app, 1)))


def test_invalid_role_is_rejected(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    for bad in (0, 3, 255):
        with rejected(R_ROLE):
            helpers.verify_code(app, bob, bad, b"\x01" * 64)
    helpers.verify_code(app, bob, 2, sign(sk_b, message_for(app, 2)))     # شاهد


def test_key_rotation_obsoletes_old_key(alice, bob):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    old_sig = sign(sk_s, message_for(app, 1))
    helpers.verify_code(app, bob, 1, old_sig)                     # پیش از تعویض معتبر
    sk_new, pk_new = keypair()
    helpers.rotate_key(app, alice, pk_new)
    with rejected(R_SIG):
        helpers.verify_code(app, bob, 1, old_sig)                 # کلید قبلی منسوخ شد
    helpers.verify_code(app, bob, 1, sign(sk_new, message_for(app, 1)))   # شاهد: کلید تازه معتبر است


def test_anyone_may_verify_and_nothing_changes(alice, bob, mallory):
    app, sk_b, sk_s = locked_app_with_keys(alice, bob)
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.verify_code(app, mallory, 1, sign(sk_s, message_for(app, 1)))   # فراخواننده‌ی بیگانه
    assert helpers.balance(addr) == before_bal
    assert helpers.read_state(app) == before
