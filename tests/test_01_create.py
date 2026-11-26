"""
مرحله‌ی ۱: ساخت قرارداد.
هر رد‌شدن دو چیز را ثابت می‌کند: (۱) رد شد، (۲) به همان دلیلِ مورد انتظار رد شد
(پیام assert از روی TEAL و pc خوانده می‌شود)، و یک «شاهد موفق» با ورودی درست هم دارد.
"""
import pytest

import config
import helpers
from helpers import ALGO, AlgodHTTPError, rejected

DAY = 86_400

# پیام‌های assert قرارداد (باید با contracts/lmarket.py یکی باشند)
R_SAME = "buyer and seller must differ"
R_OUTSIDER = "only buyer or seller may create"
R_AGREED = "agreed below minimum"
R_DUE_LOW = "due_secs below minimum"
R_DUE_HIGH = "due_secs above maximum"


def make(creator, buyer, seller, agreed=5 * ALGO, due=7 * DAY):
    return helpers.deploy(creator, buyer.address, seller.address, agreed, due)


# ---------------------------------------------------------------- مسیر موفق
def test_seller_can_create_and_state_is_recorded(alice, bob):
    app = make(alice, bob, alice)
    s = helpers.read_state(app)
    assert s["creator"] == alice.address
    assert s["buyer"] == bob.address
    assert s["seller"] == alice.address
    assert s["agreed"] == 5 * ALGO
    assert s["due_secs"] == 7 * DAY
    assert s["created_at"] > 0


def test_buyer_can_create(alice, bob):
    app = make(bob, bob, alice)
    assert helpers.read_state(app)["creator"] == bob.address


# ---------------------------------------------------------------- اعتبارسنجی
def test_outsider_cannot_create(alice, bob, mallory):
    make(alice, bob, alice)                       # شاهد: خود طرف مجاز است
    with rejected(R_OUTSIDER):
        make(mallory, bob, alice)


def test_buyer_and_seller_must_differ(alice, bob):
    make(alice, bob, alice)                       # شاهد
    with rejected(R_SAME):
        make(alice, alice, alice)


@pytest.mark.parametrize("agreed,ok", [
    (config.MIN_AGREED - 1, False),
    (config.MIN_AGREED, True),                    # مرز دقیق باید پذیرفته شود
    (config.MIN_AGREED + 1, True),
    (0, False),
])
def test_agreed_boundaries(alice, bob, agreed, ok):
    if ok:
        make(alice, bob, alice, agreed=agreed)
    else:
        with rejected(R_AGREED):
            make(alice, bob, alice, agreed=agreed)


@pytest.mark.parametrize("due,ok,reason", [
    (config.MIN_DUE_SECS - 1, False, R_DUE_LOW),
    (config.MIN_DUE_SECS, True, None),
    (config.MAX_DUE_SECS, True, None),
    (config.MAX_DUE_SECS + 1, False, R_DUE_HIGH),
    (0, False, R_DUE_LOW),
])
def test_due_boundaries(alice, bob, due, ok, reason):
    if ok:
        make(alice, bob, alice, due=due)
    else:
        with rejected(reason):
            make(alice, bob, alice, due=due)


# ---------------------------------------------------------------- تغییرناپذیری
@pytest.mark.parametrize("kind", ["update", "delete", "optin"])
def test_program_is_immutable(alice, bob, kind):
    app = make(alice, bob, alice)
    with pytest.raises(AlgodHTTPError):
        helpers.raw_app_txn(alice, kind, app)     # حتی خود سازنده هم نمی‌تواند
    assert helpers.read_state(app)["creator"] == alice.address   # قرارداد هنوز زنده است
