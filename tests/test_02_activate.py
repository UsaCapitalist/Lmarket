"""
مرحله‌ی ۲: فعال‌سازی با پرداخت APP_FUND.
هر رد‌شدن دو چیز را ثابت می‌کند: رد شد، و به همان پیام assert مورد انتظار رد شد.
"""
import config
import helpers
from helpers import ALGO, rejected

DAY = 86_400

R_ALREADY = "already activated"
R_CREATOR = "only creator may activate"
R_SENDER = "payment sender must be creator"
R_RECEIVER = "payment must go to the contract"
R_AMOUNT = "activation payment must equal APP_FUND"


def fresh_app(alice, bob):
    """قراردادی که ساخته شده و هنوز فعال نیست."""
    return helpers.deploy(alice, bob.address, alice.address, 5 * ALGO, 7 * DAY)


# ---------------------------------------------------------------- مسیر موفق
def test_creator_activates_with_exact_fund(alice, bob):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    assert helpers.read_state(app)["activated"] == 1


def test_contract_account_holds_at_least_min_balance_after_activation(alice, bob):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    addr = helpers.app_address(app)
    assert helpers.balance(addr) == config.APP_FUND
    # شاهد واقعی برای مقدار APP_FUND: موجودی باید از حداقل لازم شبکه بیشتر یا برابر باشد
    assert helpers.balance(addr) >= helpers.min_balance(addr)


def test_buyer_creator_can_activate(alice, bob):
    app = helpers.deploy(bob, bob.address, alice.address, 5 * ALGO, 7 * DAY)
    helpers.activate(app, bob, config.APP_FUND)
    assert helpers.read_state(app)["activated"] == 1


# ---------------------------------------------------------------- اعتبارسنجی
def test_counterparty_cannot_activate(alice, bob):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)        # شاهد: سازنده فعال می‌کند
    app2 = fresh_app(alice, bob)
    with rejected(R_CREATOR):
        helpers.activate(app2, bob, config.APP_FUND)


def test_outsider_cannot_activate(alice, bob, mallory):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)        # شاهد
    app2 = fresh_app(alice, bob)
    with rejected(R_CREATOR):
        helpers.activate(app2, mallory, config.APP_FUND)


def test_wrong_amount_is_rejected(alice, bob):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)        # شاهد
    app2 = fresh_app(alice, bob)
    with rejected(R_AMOUNT):
        helpers.activate(app2, alice, config.APP_FUND - 1)
    with rejected(R_AMOUNT):
        helpers.activate(app2, alice, config.APP_FUND + 1)


def test_payment_to_wrong_receiver_is_rejected(alice, bob, mallory):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)        # شاهد
    app2 = fresh_app(alice, bob)
    with rejected(R_RECEIVER):
        helpers.activate(app2, alice, config.APP_FUND, receiver=mallory.address)


def test_activation_is_one_time(alice, bob):
    app = fresh_app(alice, bob)
    helpers.activate(app, alice, config.APP_FUND)
    with rejected(R_ALREADY):
        helpers.activate(app, alice, config.APP_FUND)
    assert helpers.read_state(app)["activated"] == 1
