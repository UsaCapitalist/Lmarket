"""
مرحله‌ی ۳الف: واریز و برداشت (هنوز قفلی وجود ندارد).
هر رد‌شدن دو چیز را ثابت می‌کند: رد شد، و به همان پیام assert مورد انتظار رد شد؛
و هر رد‌شدن یک «شاهد موفق» با ورودی درست دارد.
"""
import config
import helpers
from helpers import ALGO, WITHDRAW_FEE, rejected

DAY = 86_400

R_NOT_ACTIVE = "contract not activated"
R_DEP_PARTY = "only buyer or seller may deposit"
R_DEP_SENDER = "deposit payment sender must be the caller"
R_DEP_RECEIVER = "deposit must go to the contract"
R_DEP_ZERO = "deposit must be positive"
R_WD_PARTY = "only buyer or seller may withdraw"
R_WD_ZERO = "withdraw must be positive"
R_WD_EXCEEDS = "withdraw exceeds deposit"


def active_app(alice, bob):
    """قرارداد فعال‌شده؛ آلیس فروشنده و سازنده، باب خریدار."""
    app = helpers.deploy(alice, bob.address, alice.address, 5 * ALGO, 7 * DAY)
    helpers.activate(app, alice, config.APP_FUND)
    return app


# ---------------------------------------------------------------- واریز
def test_buyer_deposit_is_recorded_and_held(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 2 * ALGO)
    s = helpers.read_state(app)
    assert s["buyer_dep"] == 2 * ALGO
    assert s["seller_dep"] == 0
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * ALGO


def test_each_party_sees_the_others_deposit(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 2 * ALGO)
    helpers.deposit(app, alice, 3 * ALGO)
    s = helpers.read_state(app)           # همان حافظه‌ی عمومی که هر دو طرف می‌خوانند
    assert (s["buyer_dep"], s["seller_dep"]) == (2 * ALGO, 3 * ALGO)


def test_deposits_accumulate(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)
    helpers.deposit(app, bob, 2 * ALGO)
    assert helpers.read_state(app)["buyer_dep"] == 3 * ALGO


def test_deposit_requires_activation(alice, bob):
    active_app(alice, bob)                                    # شاهد: پس از فعال‌سازی مجاز است
    app = helpers.deploy(alice, bob.address, alice.address, 5 * ALGO, 7 * DAY)
    with rejected(R_NOT_ACTIVE):
        helpers.deposit(app, bob, 1 * ALGO)


def test_outsider_cannot_deposit(alice, bob, mallory):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)                       # شاهد
    with rejected(R_DEP_PARTY):
        helpers.deposit(app, mallory, 1 * ALGO)


def test_zero_deposit_is_rejected(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1)                              # شاهد: کوچک‌ترین مبلغ مثبت
    with rejected(R_DEP_ZERO):
        helpers.deposit(app, bob, 0)


def test_payment_to_wrong_receiver_is_rejected(alice, bob, mallory):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)                       # شاهد
    with rejected(R_DEP_RECEIVER):
        helpers.deposit(app, bob, 1 * ALGO, receiver=mallory.address)


def test_payment_must_come_from_the_caller(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)                       # شاهد
    # باب فراخوانی می‌کند ولی آلیس پرداخت می‌کند: واریزی باب نباید افزایش یابد
    with rejected(R_DEP_SENDER):
        helpers.deposit(app, bob, 1 * ALGO, pay_from=alice)
    assert helpers.read_state(app)["buyer_dep"] == 1 * ALGO


# ---------------------------------------------------------------- برداشت
def test_partial_withdraw_returns_exact_amount(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 3 * ALGO)
    before = helpers.balance(bob.address)
    helpers.withdraw(app, bob, 1 * ALGO)
    assert helpers.read_state(app)["buyer_dep"] == 2 * ALGO
    assert helpers.balance(bob.address) == before + 1 * ALGO - WITHDRAW_FEE
    assert helpers.balance(helpers.app_address(app)) == config.APP_FUND + 2 * ALGO


def test_full_withdraw_leaves_base_balance_untouched(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 3 * ALGO)
    helpers.withdraw(app, bob, 3 * ALGO)                      # دقیقاً همه‌ی واریزی
    assert helpers.read_state(app)["buyer_dep"] == 0
    addr = helpers.app_address(app)
    assert helpers.balance(addr) == config.APP_FUND           # موجودی پایه‌ی قرارداد دست‌نخورده
    assert helpers.balance(addr) >= helpers.min_balance(addr)


def test_cannot_withdraw_more_than_own_deposit(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)
    helpers.withdraw(app, bob, 1 * ALGO)                      # شاهد: برداشت دقیق مجاز است
    helpers.deposit(app, bob, 1 * ALGO)
    with rejected(R_WD_EXCEEDS):
        helpers.withdraw(app, bob, 1 * ALGO + 1)


def test_cannot_withdraw_the_other_partys_deposit(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 2 * ALGO)
    helpers.deposit(app, alice, 1 * ALGO)
    helpers.withdraw(app, alice, 1 * ALGO)                    # شاهد: از واریزی خودش مجاز است
    with rejected(R_WD_EXCEEDS):
        helpers.withdraw(app, alice, 1)                       # واریزی آلیس صفر شده؛ از مال باب نمی‌تواند
    assert helpers.read_state(app)["buyer_dep"] == 2 * ALGO


def test_outsider_cannot_withdraw(alice, bob, mallory):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)
    helpers.withdraw(app, bob, 1)                             # شاهد
    with rejected(R_WD_PARTY):
        helpers.withdraw(app, mallory, 1)


def test_zero_withdraw_is_rejected(alice, bob):
    app = active_app(alice, bob)
    helpers.deposit(app, bob, 1 * ALGO)
    helpers.withdraw(app, bob, 1)                             # شاهد
    with rejected(R_WD_ZERO):
        helpers.withdraw(app, bob, 0)
