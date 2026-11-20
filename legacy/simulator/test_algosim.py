"""تست‌های خصمانه‌ی قرارداد Lmarket روی شبیه‌ساز.  اجرا:  python3 -m pytest -q test_algosim.py"""
import random

import pytest

from algosim import (ALGO, EVIL_HASH, OFFICIAL_HASH, LmarketV1, SubmitError, build_group,
                     code_for, make_demo_world, release_manifest, verify_release, SETTINGS,
                     app_address, app_min_balance, Wallet, Chain, group_id_of)

DAY = 86400


class Env:
    def __init__(self):
        self.chain, self.W = make_demo_world(clock=lambda: 1_800_000_000)
        self.A, self.B, self.M = self.W["Alice"], self.W["Bob"], self.W["Mallory"]  # فروشنده، خریدار، مهاجم

    def send(self, w, intent, expect="confirmed", block=True):
        txns, _ = build_group(self.chain, w.address, intent)
        gid = self.chain.submit([w.sign_txn(t) for t in txns])
        if block:
            self.chain.produce_block()
        st = self.chain.tx_status(gid)
        assert st["status"] == expect, st
        return st

    def fails(self, w, intent, text=None):
        """تراکنش باید همان لحظه‌ی ارسال رد شود"""
        txns, _ = build_group(self.chain, w.address, intent)
        with pytest.raises(SubmitError) as e:
            self.chain.submit([w.sign_txn(t) for t in txns])
        if text:
            assert text in str(e.value), str(e.value)

    def new_app(self, agreed=5 * ALGO, creator=None, fund=True, **kw):
        creator = creator or self.A
        h = kw.pop("approval_hash", OFFICIAL_HASH)
        before = self.chain.next_app_id
        self.send(creator, dict(kind="create", buyer=self.B.address, seller=self.A.address,
                                agreed=agreed, due_secs=7 * DAY, approval_hash=h))
        app_id = before
        if fund:
            self.send(creator, dict(kind="init", app_id=app_id))
        return app_id

    def st(self, app_id):
        return self.chain.app_info(app_id)["state"]

    def code(self, w, app_id, kind):
        return code_for(w, self.chain, self.chain.app_info(app_id), kind)

    def bal(self, w):
        return self.chain.balance(w.address)


@pytest.fixture
def e():
    return Env()


def lock_both(e, app, a=5 * ALGO, b=5 * ALGO):
    e.send(e.A, dict(kind="deposit", app_id=app, amount=a))
    e.send(e.B, dict(kind="deposit", app_id=app, amount=b))


# ---------------------------------------------------------------- مسیر موفق
def test_full_happy_path_and_conservation(e):
    a0, b0 = e.bal(e.A), e.bal(e.B)
    app = e.new_app()
    lock_both(e, app)
    s = e.st(app)
    assert s["locked"] == 1 and s["dep_b"] == s["dep_s"] == 5 * ALGO
    e.send(e.B, dict(kind="mark_paid", app_id=app))
    e.send(e.A, dict(kind="mark_shipped", app_id=app))
    pay_code = e.code(e.A, app, LmarketV1.KIND_PAY)      # فروشنده: «وجه دریافت شد»
    goods_code = e.code(e.B, app, LmarketV1.KIND_GOODS)  # خریدار: «کالا دریافت شد»
    e.send(e.B, dict(kind="enter_code", app_id=app, code=pay_code))
    assert not e.st(app)["settled_at"], "با یک کد نباید تسویه شود"
    assert e.chain.balance(app_address(app)) == 10 * ALGO + LmarketV1.APP_FUND
    e.send(e.A, dict(kind="enter_code", app_id=app, code=goods_code))
    s = e.st(app)
    assert s["settled_at"] and s["dep_b"] == s["dep_s"] == 0
    assert e.chain.balance(app_address(app)) == LmarketV1.APP_FUND
    # فقط کارمزد و ذخیره‌ی ساخت از کیف‌ها کم شده؛ وثیقه‌ها برگشته‌اند
    assert e.bal(e.B) == b0 - 2000 - 1000 - 3000  # deposit(2 tx) + mark_paid + enter_code؛ وثیقه کامل برگشته
    assert e.chain.supply_check() == e.chain.total_supply


def test_creator_reclaims_reserve_after_settlement(e):
    app = e.new_app()
    lock_both(e, app)
    e.fails(e.A, dict(kind="delete", app_id=app), "تسویه")
    e.send(e.B, dict(kind="mark_paid", app_id=app))
    e.send(e.A, dict(kind="mark_shipped", app_id=app))
    e.send(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.A, app, LmarketV1.KIND_PAY)))
    e.send(e.A, dict(kind="enter_code", app_id=app, code=e.code(e.B, app, LmarketV1.KIND_GOODS)))
    before = e.bal(e.A)
    e.fails(e.B, dict(kind="delete", app_id=app), "سازنده")
    e.send(e.A, dict(kind="delete", app_id=app))
    assert not e.chain.app_info(app)["exists"]
    assert e.bal(e.A) == before - 2000 + LmarketV1.APP_FUND
    assert e.chain.min_balance(e.A.address) == 100_000
    assert e.chain.supply_check() == e.chain.total_supply


# ---------------------------------------------------------------- قفل دقیق و مازاد
def test_lock_exactly_agreed_amount_and_surplus_is_free(e):
    app = e.new_app()
    e.send(e.A, dict(kind="deposit", app_id=app, amount=8 * ALGO))
    assert e.st(app)["locked"] == 0
    e.send(e.B, dict(kind="deposit", app_id=app, amount=5 * ALGO))
    assert e.st(app)["locked"] == 1
    e.fails(e.A, dict(kind="withdraw", app_id=app, amount=3 * ALGO + 1), "قفل")
    e.send(e.A, dict(kind="withdraw", app_id=app, amount=3 * ALGO))
    assert e.st(app)["dep_s"] == 5 * ALGO
    e.fails(e.B, dict(kind="withdraw", app_id=app, amount=1), "قفل")
    e.fails(e.A, dict(kind="deposit", app_id=app, amount=ALGO), "قفل")


def test_partial_deposits_accumulate_until_lock(e):
    app = e.new_app()
    e.send(e.A, dict(kind="deposit", app_id=app, amount=2 * ALGO))
    e.send(e.A, dict(kind="deposit", app_id=app, amount=3 * ALGO))
    e.send(e.B, dict(kind="deposit", app_id=app, amount=4 * ALGO))
    assert e.st(app)["locked"] == 0
    e.send(e.B, dict(kind="deposit", app_id=app, amount=ALGO))
    assert e.st(app)["locked"] == 1


def test_cancel_before_lock_and_both_withdraw(e):
    a0, b0 = e.bal(e.A), e.bal(e.B)
    app = e.new_app()
    e.send(e.A, dict(kind="deposit", app_id=app, amount=5 * ALGO))
    e.send(e.B, dict(kind="deposit", app_id=app, amount=2 * ALGO))
    e.send(e.A, dict(kind="withdraw", app_id=app, amount=5 * ALGO))
    e.send(e.B, dict(kind="withdraw", app_id=app, amount=2 * ALGO))
    assert e.chain.balance(app_address(app)) == LmarketV1.APP_FUND   # هیچ پولی بلوکه نشده
    assert e.bal(e.B) == b0 - 2000 - 2000   # فقط کارمزدِ واریز و برداشت
    assert e.st(app)["dep_b"] == e.st(app)["dep_s"] == 0


def test_race_withdraw_vs_second_deposit_same_block(e):
    """اگر برداشت قبل از واریز دوم در بلوک بیاید، قفل نمی‌شود؛ اگر بعد از آن، قفل است و برداشت رد می‌شود."""
    for order in ("withdraw_first", "deposit_first"):
        app = e.new_app()
        e.send(e.A, dict(kind="deposit", app_id=app, amount=5 * ALGO))
        t_dep, _ = build_group(e.chain, e.B.address, dict(kind="deposit", app_id=app, amount=5 * ALGO))
        t_wd, _ = build_group(e.chain, e.A.address, dict(kind="withdraw", app_id=app, amount=5 * ALGO))
        g_dep = e.chain.submit([e.B.sign_txn(t) for t in t_dep])
        g_wd = e.chain.submit([e.A.sign_txn(t) for t in t_wd])
        if order == "withdraw_first":
            e.chain.pool.reverse()
        e.chain.produce_block()
        sd, sw = e.chain.tx_status(g_dep), e.chain.tx_status(g_wd)
        if order == "deposit_first":
            assert sd["status"] == "confirmed" and sw["status"] == "rejected"
            assert e.st(app)["locked"] == 1
        else:
            assert sw["status"] == "confirmed" and sd["status"] == "confirmed"
            assert e.st(app)["locked"] == 0 and e.st(app)["dep_b"] == 5 * ALGO
        assert e.chain.supply_check() == e.chain.total_supply


# ---------------------------------------------------------------- باج‌گیری / قفل بی‌پایان
def test_vanishing_seller_nobody_can_take_anything_even_after_years(e):
    app = e.new_app()
    lock_both(e, app)
    e.send(e.B, dict(kind="mark_paid", app_id=app))
    e.chain.advance(10 * 365 * DAY)
    assert e.chain.reputation(e.A.address)["overdue_open"] >= 1
    for w in (e.A, e.B, e.M):
        for amt in (1, 5 * ALGO, 10 * ALGO):
            e.fails(w, dict(kind="withdraw", app_id=app, amount=amt))
    e.fails(e.A, dict(kind="delete", app_id=app))
    assert e.chain.balance(app_address(app)) == 10 * ALGO + LmarketV1.APP_FUND
    assert e.st(app)["locked"] == 1 and not e.st(app)["settled_at"]


def test_cheater_loses_collateral_too(e):
    """فروشنده پول را گرفته و ناپدید می‌شود: وثیقه‌ی خودش هم تا ابد قفل است (اهرم متقابل)"""
    app = e.new_app()
    lock_both(e, app)
    free_after = e.st(app)["dep_s"] - e.st(app)["agreed"]
    assert free_after == 0
    e.fails(e.A, dict(kind="withdraw", app_id=app, amount=1))


def test_timer_never_releases_funds(e):
    app = e.new_app()
    lock_both(e, app)
    e.chain.advance(400 * DAY)
    assert e.chain.reputation(e.A.address)["overdue_open"] >= 1
    assert e.st(app)["locked"] == 1
    e.fails(e.B, dict(kind="withdraw", app_id=app, amount=ALGO))


# ---------------------------------------------------------------- جعل کد
def test_code_forgery_matrix(e):
    app = e.new_app()
    app2 = e.new_app()
    for a in (app, app2):
        lock_both(e, a)
        e.send(e.B, dict(kind="mark_paid", app_id=a))
        e.send(e.A, dict(kind="mark_shipped", app_id=a))
    good_pay = e.code(e.A, app, LmarketV1.KIND_PAY)
    # ۱) امضای شخص ثالث
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.M, app, LmarketV1.KIND_PAY)), "معتبر")
    # ۲) خریدار کد خودش را به‌جای کد فروشنده وارد کند
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.B, app, LmarketV1.KIND_PAY)), "معتبر")
    # ۳) کد قرارداد دیگر (replay بین قراردادها)
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.A, app2, LmarketV1.KIND_PAY)), "معتبر")
    # ۴) نوع پیام اشتباه (کد «کالا» به‌جای «وجه»)
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.A, app, LmarketV1.KIND_GOODS)), "معتبر")
    # ۵) متن تصادفی و طول اشتباه
    e.fails(e.B, dict(kind="enter_code", app_id=app, code="ABCDEFGH"), "طول")
    e.fails(e.B, dict(kind="enter_code", app_id=app, code="!!!"), "")
    # ۶) کد درست کار می‌کند، و با خط تیره/حروف کوچک هم
    pretty = "-".join(good_pay[i:i + 8] for i in range(0, len(good_pay), 8)).lower()
    e.send(e.B, dict(kind="enter_code", app_id=app, code=pretty))
    # ۷) ثبت دوباره‌ی همان کد
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=good_pay), "قبلاً")


def test_code_requires_prior_flag(e):
    app = e.new_app()
    lock_both(e, app)
    e.fails(e.B, dict(kind="enter_code", app_id=app, code=e.code(e.A, app, LmarketV1.KIND_PAY)), "پرداخت")
    e.fails(e.A, dict(kind="enter_code", app_id=app, code=e.code(e.B, app, LmarketV1.KIND_GOODS)), "ارسال")


def test_code_is_deterministic_so_lost_code_is_recoverable(e):
    app = e.new_app()
    assert e.code(e.A, app, LmarketV1.KIND_PAY) == e.code(e.A, app, LmarketV1.KIND_PAY)


# ---------------------------------------------------------------- دسترسی
def test_outsider_cannot_do_anything(e):
    app = e.new_app()
    e.send(e.A, dict(kind="deposit", app_id=app, amount=ALGO))
    for intent in (dict(kind="deposit", app_id=app, amount=ALGO), dict(kind="withdraw", app_id=app, amount=1),
                   dict(kind="mark_paid", app_id=app), dict(kind="mark_shipped", app_id=app),
                   dict(kind="enter_code", app_id=app, code="A" * 103), dict(kind="init", app_id=app),
                   dict(kind="delete", app_id=app)):
        e.fails(e.M, intent)


def test_wrong_role_actions(e):
    app = e.new_app()
    lock_both(e, app)
    e.fails(e.A, dict(kind="mark_paid", app_id=app), "خریدار")
    e.fails(e.B, dict(kind="mark_shipped", app_id=app), "فروشنده")


def test_create_validation(e):
    base = dict(kind="create", buyer=e.B.address, seller=e.A.address, agreed=5 * ALGO, due_secs=7 * DAY)
    e.fails(e.M, base, "فقط خریدار یا فروشنده")
    e.fails(e.A, {**base, "agreed": 1000}, "حداقل")
    e.fails(e.A, {**base, "due_secs": 5}, "مهلت")
    e.fails(e.A, {**base, "buyer": e.A.address}, "یکی")
    e.fails(e.A, {**base, "buyer": "NOTANADDRESS"}, "نامعتبر")
    e.fails(e.A, {**base, "approval_hash": "00" * 32}, "ناشناخته")


def test_deposit_requires_init_and_correct_payment(e):
    app = e.new_app(fund=False)
    e.fails(e.A, dict(kind="deposit", app_id=app, amount=ALGO), "فعال")
    e.send(e.A, dict(kind="init", app_id=app))
    e.fails(e.A, dict(kind="init", app_id=app), "قبلاً")
    # پرداخت به آدرس دیگر در گروه
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    txns[0]["receiver"] = e.M.address
    gid = group_id_of(txns)
    for t in txns:
        t["group"] = gid
    with pytest.raises(SubmitError):
        e.chain.submit([e.A.sign_txn(t) for t in txns])
    # بدون تراکنش پرداخت
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    solo = txns[1]
    solo.pop("group")
    with pytest.raises(SubmitError):
        e.chain.submit([e.A.sign_txn(solo)])


# ---------------------------------------------------------------- اتمیک بودن و کارمزد و حداقل موجودی
def test_failed_group_reverts_payment(e):
    app = e.new_app()
    before = e.bal(e.M)
    txns, _ = build_group(e.chain, e.M.address, dict(kind="deposit", app_id=app, amount=ALGO))
    with pytest.raises(SubmitError):
        e.chain.submit([e.M.sign_txn(t) for t in txns])
    assert e.bal(e.M) == before
    assert e.chain.balance(app_address(app)) == LmarketV1.APP_FUND


def test_fee_too_low_rejected(e):
    app = e.new_app()
    lock_both(e, app, 6 * ALGO, 5 * ALGO)
    txns, _ = build_group(e.chain, e.A.address, dict(kind="withdraw", app_id=app, amount=ALGO))
    txns[0]["fee"] = 1000   # برداشت تراکنش داخلی دارد و ۲۰۰۰ می‌خواهد
    with pytest.raises(SubmitError) as ex:
        e.chain.submit([e.A.sign_txn(t) for t in txns])
    assert "کارمزد" in str(ex.value)


def test_min_balance_enforced(e):
    poor = Wallet("Poor")
    e.chain.fund(poor.address, 150_000)
    txns, _ = build_group(e.chain, poor.address, dict(kind="create", buyer=e.B.address, seller=poor.address,
                                                      agreed=ALGO, due_secs=7 * DAY))
    with pytest.raises(SubmitError) as ex:
        e.chain.submit([poor.sign_txn(t) for t in txns])
    assert "حداقل" in str(ex.value)
    # حساب جدید باید دست‌کم حداقل موجودی بگیرد
    t = dict(type="pay", sender=e.A.address, receiver=Wallet("Fresh").address, amount=5000, fee=1000,
             first_valid=e.chain.round, last_valid=e.chain.round + 10, genesis=e.chain.genesis_id)
    with pytest.raises(SubmitError):
        e.chain.submit([e.A.sign_txn(t)])


def test_creation_cost_is_reserved_for_creator(e):
    before = e.chain.min_balance(e.A.address)
    e.new_app()
    assert e.chain.min_balance(e.A.address) == before + app_min_balance()


# ---------------------------------------------------------------- تکرار، انقضا، حذف از شبکه
def test_replay_rejected(e):
    app = e.new_app()
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    signed = [e.A.sign_txn(t) for t in txns]
    e.chain.submit(signed)
    e.chain.produce_block()
    with pytest.raises(SubmitError) as ex:
        e.chain.submit(signed)
    assert "تکراری" in str(ex.value)


def test_tampered_signature_and_wrong_genesis(e):
    app = e.new_app()
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    signed = [e.A.sign_txn(t) for t in txns]
    signed[0]["txn"]["amount"] = 999 * ALGO   # دستکاری بعد از امضا
    with pytest.raises(SubmitError):
        e.chain.submit(signed)
    txns, _ = build_group(e.chain, e.A.address, dict(kind="mark_paid", app_id=app))
    txns[0]["genesis"] = "other-chain"
    with pytest.raises(SubmitError):
        e.chain.submit([e.A.sign_txn(txns[0])])


def test_dropped_tx_expires_and_state_unchanged(e):
    app = e.new_app()
    e.chain.set_fault(drop_next=1)
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    gid = e.chain.submit([e.A.sign_txn(t) for t in txns])
    e.chain.produce_block()
    assert e.chain.tx_status(gid)["status"] == "pending"
    assert e.st(app)["dep_s"] == 0
    e.chain.advance(2000 * 3)
    assert e.chain.tx_status(gid)["status"] == "expired"


def test_offline_and_paused_faults(e):
    app = e.new_app()
    e.chain.set_fault(offline=True)
    txns, _ = build_group(e.chain, e.A.address, dict(kind="deposit", app_id=app, amount=ALGO))
    with pytest.raises(SubmitError):
        e.chain.submit([e.A.sign_txn(t) for t in txns])
    e.chain.set_fault(offline=False, paused=True)
    gid = e.chain.submit([e.A.sign_txn(t) for t in txns])
    assert e.chain.produce_block() is None
    assert e.chain.tx_status(gid)["status"] == "pending"
    e.chain.set_fault(paused=False)
    e.chain.produce_block()
    assert e.chain.tx_status(gid)["status"] == "confirmed"


def test_partial_creation_can_resume(e):
    app = e.new_app(fund=False)       # ساخته شد ولی فعال نشد (مثلاً قطع اینترنت وسط کار)
    assert e.st(app)["active"] == 0
    rep = e.chain.reputation(e.A.address)
    e.send(e.A, dict(kind="init", app_id=app))
    assert e.st(app)["active"] == 1
    assert e.chain.reputation(e.A.address)["total"] == rep["total"]   # هنوز واریزی نیست؛ حساب نمی‌شود
    e.send(e.A, dict(kind="deposit", app_id=app, amount=ALGO))
    assert e.chain.reputation(e.A.address)["total"] == rep["total"] + 1


# ---------------------------------------------------------------- امضای ناشر و نسخه
def test_release_signature_detects_tampered_program(e):
    manifest = release_manifest()
    good = e.new_app()
    assert e.chain.app_info(good)["approval_hash"] == OFFICIAL_HASH
    assert verify_release(manifest, "1.0.0", OFFICIAL_HASH)
    evil = e.new_app(approval_hash=EVIL_HASH)
    info = e.chain.app_info(evil)
    assert info["state"]["version"] == "1.0.0"                 # ادعای نسخه‌ی رسمی
    assert not verify_release(manifest, info["state"]["version"], info["approval_hash"])
    forged = {**manifest, "publisher": Wallet("x").address and manifest["publisher"]}
    forged["releases"] = [{**manifest["releases"][0], "approval_hash": EVIL_HASH}]
    assert not verify_release(forged, "1.0.0", EVIL_HASH)       # امضای ناشر روی هش دیگر معتبر نیست


def test_evil_program_really_steals_so_check_matters(e):
    evil = e.new_app(approval_hash=EVIL_HASH)
    lock_both(e, evil)
    e.send(e.A, dict(kind="withdraw", app_id=evil, amount=9 * ALGO))      # فروشنده وثیقه‌ی خریدار را هم برد
    assert e.chain.balance(app_address(evil)) < 10 * ALGO


# ---------------------------------------------------------------- اعتبار
def test_reputation_numbers(e):
    r_alice, r_dave, r_mal = (e.chain.reputation(e.W[n].address) for n in ("Alice", "Dave", "Mallory"))
    assert r_alice["settled"] == 14 and r_alice["open"] == 0 and r_alice["wallet_age_days"] >= 799
    assert r_dave["open"] == 20 and r_dave["overdue_open"] == 18 and r_dave["wallet_age_days"] in (119, 120)
    assert r_mal["total"] == 0 and r_mal["wallet_age_days"] == 0


def test_reputation_moves_with_real_contracts(e):
    app = e.new_app()
    lock_both(e, app)
    before = e.chain.reputation(e.B.address)
    assert before["open"] >= 1
    e.chain.advance(8 * DAY)   # هشت روز: هم قرارداد تازه (۷ روزه) و هم قرارداد باز قدیمیِ بابِ (۵ روز مانده) عقب می‌افتند
    after = e.chain.reputation(e.B.address)
    assert after["overdue_open"] == before["open"] == 2


def test_events_are_indexed(e):
    app = e.new_app()
    lock_both(e, app)
    kinds = [x["kind"] for x in e.chain.events_for(app)]
    assert kinds == ["created", "activated", "deposit", "deposit", "locked"]


# ---------------------------------------------------------------- فاز رندوم: ثابت‌ها (invariants)
def test_random_fuzz_invariants():
    rnd = random.Random(1234)
    for episode in range(12):
        e = Env()
        apps = []
        players = [e.A, e.B, e.M]
        for step in range(250):
            w = rnd.choice(players)
            roll = rnd.random()
            try:
                if roll < 0.05 or not apps:
                    intent = dict(kind="create", buyer=e.B.address, seller=e.A.address,
                                  agreed=rnd.choice([ALGO, 3 * ALGO]), due_secs=7 * DAY)
                    txns, _ = build_group(e.chain, w.address, intent)
                    e.chain.submit([w.sign_txn(t) for t in txns])
                    e.chain.produce_block()
                    apps.append(e.chain.next_app_id - 1)
                    continue
                app = rnd.choice(apps)
                info = e.chain.app_info(app)
                if not info["exists"]:
                    continue
                kind = rnd.choice(["init", "deposit", "deposit", "withdraw", "mark_paid", "mark_shipped",
                                   "code", "code", "delete"])
                if kind == "code":
                    other = e.A if w is e.B else e.B
                    sig_kind = LmarketV1.KIND_PAY if w is e.B else LmarketV1.KIND_GOODS
                    signer = rnd.choice([other, w, e.M])
                    intent = dict(kind="enter_code", app_id=app, code=code_for(signer, e.chain, info, sig_kind))
                elif kind in ("deposit", "withdraw"):
                    intent = dict(kind=kind, app_id=app, amount=rnd.choice([1, ALGO // 2, ALGO, 2 * ALGO]))
                else:
                    intent = dict(kind=kind, app_id=app)
                txns, _ = build_group(e.chain, w.address, intent)
                e.chain.submit([w.sign_txn(t) for t in txns])
                e.chain.produce_block()
            except SubmitError:
                pass
            # ثابت‌ها
            assert e.chain.supply_check() == e.chain.total_supply
            for a in apps:
                i = e.chain.app_info(a)
                if not i["exists"]:
                    continue
                s = i["state"]
                if s["active"]:
                    assert i["balance"] == LmarketV1.APP_FUND + s["dep_b"] + s["dep_s"], (s, i["balance"])
                if s["locked"] and not s["settled_at"]:
                    assert s["dep_b"] >= s["agreed"] and s["dep_s"] >= s["agreed"]
                if s["settled_at"]:
                    assert s["ent_b"] and s["ent_s"]
                assert not (s["ent_b"] and not s["paid_at"])
                assert not (s["ent_s"] and not s["shipped_at"])
            for acct in e.chain.accounts:
                b = e.chain.balance(acct)
                assert b == 0 or b >= e.chain.min_balance(acct) or acct == e.chain.dispenser_addr


# ---------------------------------------------------------------- بازبینی: رهاشده، تسویه‌ی امن، آدرس، زنجیره
def test_create_status_reports_app_id(e):
    st = e.send(e.A, dict(kind="create", buyer=e.B.address, seller=e.A.address, agreed=5 * ALGO, due_secs=7 * DAY))
    assert st["app_id"] == e.chain.next_app_id - 1


def test_abandoned_contract_can_be_cancelled_and_all_returned(e):
    before = e.bal(e.A)
    app = e.new_app()
    e.send(e.A, dict(kind="delete", app_id=app))
    assert not e.chain.app_info(app)["exists"]
    # کارمزد: ساخت ۱۰۰۰ + فعال‌سازی (۲ تراکنش) ۲۰۰۰ + حذف ۲۰۰۰؛ ذخیره‌ی حساب قرارداد کامل برگشته
    assert e.bal(e.A) == before - 5000
    assert e.chain.supply_check() == e.chain.total_supply


def test_abandoned_contract_does_not_count_as_open(e):
    before = e.chain.reputation(e.A.address)["open"]
    app = e.new_app()
    e.send(e.A, dict(kind="delete", app_id=app))
    assert e.chain.reputation(e.A.address)["open"] == before


def test_cannot_cancel_contract_holding_deposits(e):
    app = e.new_app()
    e.send(e.A, dict(kind="deposit", app_id=app, amount=ALGO))
    e.fails(e.A, dict(kind="delete", app_id=app), "تسویه")


def test_lowercase_address_rejected(e):
    e.fails(e.A, dict(kind="create", buyer=e.B.address.lower(), seller=e.A.address,
                      agreed=5 * ALGO, due_secs=7 * DAY), "نامعتبر")


def test_code_from_previous_world_rejected():
    old = Env()
    app_old = old.new_app()
    old_code = old.code(old.A, app_old, LmarketV1.KIND_PAY)
    new = Env()
    app = new.new_app()
    assert app == app_old                        # همان شناسه‌ی قرارداد، دنیای دیگر
    lock_both(new, app)
    new.send(new.B, dict(kind="mark_paid", app_id=app))
    new.send(new.A, dict(kind="mark_shipped", app_id=app))
    new.fails(new.B, dict(kind="enter_code", app_id=app, code=old_code), "معتبر")


def test_evil_contract_settlement_refuses_and_state_stays(e):
    evil = e.new_app(approval_hash=EVIL_HASH)
    lock_both(e, evil)
    e.send(e.A, dict(kind="withdraw", app_id=evil, amount=9 * ALGO))
    e.send(e.B, dict(kind="mark_paid", app_id=evil))
    e.send(e.A, dict(kind="mark_shipped", app_id=evil))
    e.send(e.B, dict(kind="enter_code", app_id=evil, code=e.code(e.A, evil, LmarketV1.KIND_PAY)))
    e.fails(e.A, dict(kind="enter_code", app_id=evil, code=e.code(e.B, evil, LmarketV1.KIND_GOODS)), "نمی‌خواند")
    assert not e.st(evil)["settled_at"]


def test_third_party_cannot_poison_reputation(e):
    before = e.chain.reputation(e.B.address)
    e.send(e.M, dict(kind="create", buyer=e.B.address, seller=e.M.address, agreed=5 * ALGO, due_secs=7 * DAY))
    app = e.chain.next_app_id - 1
    e.send(e.M, dict(kind="init", app_id=app))
    e.send(e.M, dict(kind="deposit", app_id=app, amount=5 * ALGO))
    after = e.chain.reputation(e.B.address)
    assert after["open"] == before["open"] and after["total"] == before["total"]
