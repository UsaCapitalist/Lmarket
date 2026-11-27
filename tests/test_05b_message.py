"""
مرحله‌ی ۵پ: پیام امضا (هنوز امضایی بررسی نمی‌شود).
قرارداد پیام را از حافظه‌ی خودش می‌سازد؛ تست آن را با مرجع خالص tests/signing_message.py مقایسه می‌کند.
هر رد‌شدن پیام assert مورد انتظار را می‌سنجد و یک شاهد موفق دارد.
"""
from algosdk import encoding

import config
import helpers
import signing_message as sm
from helpers import ALGO, rejected

DAY = 86_400
AGREED = 5 * ALGO

R_LOCK = "message requires lock"
R_ROLE = "invalid role"

# بردار ثابت: رابط جاوااسکریپت بعداً باید دقیقاً همین خروجی را بسازد
VECTOR_HEX = (
    "4c4d41524b45542d563101000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    "00000000000004d2" + "0b" * 32 + "0c" * 32
    + "00000000004c4b40" "000000000009" "3a80" "00000000000003e8" "00000000000003e9" "00000000000003ea"
)


def locked_app(alice, bob, agreed=AGREED, due=7 * DAY):
    app = helpers.deploy(alice, bob.address, alice.address, agreed, due)
    helpers.activate(app, alice, config.APP_FUND)
    helpers.deposit(app, bob, agreed)
    helpers.deposit(app, alice, agreed)
    assert helpers.read_state(app)["locked"] == 1
    return app


def rich_parties():
    """چند قرارداد قفل‌شده در یک تست به ALGO بیشتری از ۱۰ ALGO فیکسچرها نیاز دارد (وثیقه + حداقل موجودی هر برنامه)."""
    return helpers.new_actor("alice_rich", funded=40 * ALGO), helpers.new_actor("bob_rich", funded=40 * ALGO)


def expected(app, role):
    s = helpers.read_state(app)
    return sm.build_message(
        role, helpers.genesis_hash(), app,
        encoding.decode_address(s["buyer"]), encoding.decode_address(s["seller"]),
        s["agreed"], s["due_secs"], s["created_at"], s["activated_at"], s["locked_at"],
    )


def test_reference_matches_fixed_vector():
    v = sm.build_message(1, bytes(range(32)), 1234, b"\x0b" * 32, b"\x0c" * 32, 5_000_000, 604_800, 1000, 1001, 1002)
    assert len(v) == sm.MESSAGE_LEN == 155
    assert v.hex() == VECTOR_HEX


def test_contract_message_equals_reference_for_both_roles(alice, bob):
    app = locked_app(alice, bob)
    for role in (1, 2):
        m = helpers.message(app, bob, role)
        assert len(m) == 155
        assert m == expected(app, role)


def test_roles_differ_only_in_the_role_byte(alice, bob):
    app = locked_app(alice, bob)
    m1, m2 = helpers.message(app, bob, 1), helpers.message(app, bob, 2)
    assert m1 != m2
    assert m1[:10] == m2[:10] and m1[11:] == m2[11:]
    assert m1[10] == 1 and m2[10] == 2


def test_message_is_not_defined_before_lock(alice, bob):
    app = helpers.deploy(alice, bob.address, alice.address, AGREED, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    helpers.deposit(app, bob, AGREED)                             # فقط یک طرف: قفل نیست
    with rejected(R_LOCK):
        helpers.message(app, bob, 1)
    helpers.deposit(app, alice, AGREED)                           # شاهد: پس از قفل تعریف می‌شود
    assert len(helpers.message(app, bob, 1)) == 155


def test_invalid_role_is_rejected(alice, bob):
    app = locked_app(alice, bob)
    for bad in (0, 3, 255):
        with rejected(R_ROLE):
            helpers.message(app, bob, bad)
    assert len(helpers.message(app, bob, 2)) == 155              # شاهد


def test_message_is_deterministic_and_caller_independent(alice, bob, mallory):
    app = locked_app(alice, bob)
    a = helpers.message(app, bob, 1)
    assert helpers.message(app, bob, 1) == a                      # تکرار: همان پیام
    assert helpers.message(app, mallory, 1) == a                  # فراخواننده روی پیام اثر ندارد


def test_different_contracts_give_different_messages():
    alice, bob = rich_parties()
    a, b = locked_app(alice, bob), locked_app(alice, bob)        # پارامترها یکی؛ شناسه‌ی قرارداد فرق دارد
    ma, mb = helpers.message(a, bob, 1), helpers.message(b, bob, 1)
    assert ma != mb
    assert ma == expected(a, 1) and mb == expected(b, 1)


def test_message_binds_agreed_amount_and_duration():
    alice, bob = rich_parties()
    a = locked_app(alice, bob, agreed=AGREED, due=7 * DAY)
    b = locked_app(alice, bob, agreed=AGREED + 1, due=7 * DAY)
    c = locked_app(alice, bob, agreed=AGREED, due=8 * DAY)
    base = helpers.message(a, bob, 1)
    assert base[11 + 32 + 8 + 64:][:8] != helpers.message(b, bob, 1)[11 + 32 + 8 + 64:][:8]   # فیلد agreed
    assert helpers.message(c, bob, 1) == expected(c, 1) and helpers.message(c, bob, 1) != base


def test_message_does_not_change_state_or_balance(alice, bob):
    app = locked_app(alice, bob)
    addr = helpers.app_address(app)
    before_bal, before = helpers.balance(addr), helpers.read_state(app)
    helpers.message(app, bob, 1)
    assert helpers.balance(addr) == before_bal
    assert helpers.read_state(app) == before
