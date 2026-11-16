"""
algosim.py - شبیه‌ساز بلاکچین Algorand برای تست رابط Lmarket (سفته‌ی دیجیتال)

این فایل «شبیه‌ساز» است، نه Algorand واقعی. هدف: رفتار مهم زنجیره را آن‌قدر وفادار
نشان دهد که رابط کاربری را بتوان بدون ریسک و بدون TestNet کامل آزمود:

  - دفتر کل با حساب‌ها، حداقل موجودی، کارمزد، رمزنگاری Ed25519 و آدرس‌های ۵۸ نویسه‌ای
  - بلوک‌ها و راند (هر چند ثانیه)، استخر تراکنش، تراکنش‌های گروهی اتمیک، بازه‌ی اعتبار
  - تراکنش داخلی (inner) قرارداد با کارمزد تجمیعی
  - قرارداد Lmarket (نسخه‌ی رسمی) + یک نسخه‌ی مخرب برای آزمودن بررسی امضا/نسخه
  - ایندکسر ساده: رویدادهای روی زنجیره و آمار اعتبار هر آدرس
  - تزریق خطا: قطع شبکه، توقف بلوک، حذف تراکنش، تأخیر
  - کیف پول شبیه‌سازی‌شده (Pera/Defly) با امضای تراکنش و امضای پیام

تنظیمات همین‌جا در SETTINGS است (طبق قاعده‌ی پروژه: بدون متغیر محیطی).
"""
import base64
import copy
import hashlib
import inspect
import os
import secrets
import json
import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# ============================================================ تنظیمات
SETTINGS = {
    "GENESIS_ID": "lmarket-sim-v1",
    "ALGO": 1_000_000,            # هر ALGO = یک میلیون microAlgo
    "MIN_FEE": 1000,              # کمترین کارمزد هر تراکنش (microAlgo)
    "ACCOUNT_MIN_BALANCE": 100_000,
    "TX_VALIDITY": 1000,          # حداکثر بازه‌ی اعتبار تراکنش (راند)
    "BLOCK_TIME": 2.8,            # ثانیه، برای بلوک‌ساز خودکار سرور
    "MAX_GROUP": 16,
    # کلید خصوصی ناشر فقط در فایلی جدا و بیرون از پوشه‌ی وب و مخزن است
    "PUBLISHER_KEY_FILE": os.path.expanduser("~/.lmarket/publisher_key.json"),
    "DISPENSER_SEED": "lmarket-dispenser-demo-seed-0001",
}

ALGO = SETTINGS["ALGO"]
MIN_FEE = SETTINGS["MIN_FEE"]


# ============================================================ ابزارهای رمزنگاری
def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def b32(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip("=")


def unb32(text: str) -> bytes:
    t = str(text).strip().upper().replace("-", "").replace(" ", "")
    return base64.b32decode(t + "=" * (-len(t) % 8))


def _checksum(pub: bytes) -> bytes:
    try:
        return hashlib.new("sha512_256", pub).digest()[-4:]
    except ValueError:  # نسخه‌هایی از OpenSSL که sha512_256 ندارند
        return hashlib.sha256(pub).digest()[-4:]


def addr_from_pub(pub: bytes) -> str:
    return b32(pub + _checksum(pub))


def pub_from_addr(addr: str) -> bytes:
    raw = unb32(addr)
    if len(raw) != 36 or _checksum(raw[:32]) != raw[32:]:
        raise ValueError("آدرس نامعتبر است")
    return raw[:32]


def is_valid_addr(addr) -> bool:
    """فقط شکل کانونیک (حروف بزرگ) پذیرفته می‌شود تا یک کیف پول دو نمایش متفاوت نداشته باشد."""
    try:
        return isinstance(addr, str) and len(addr) == 58 and addr == addr.upper() and bool(pub_from_addr(addr))
    except Exception:
        return False


def app_address(app_id: int) -> str:
    return addr_from_pub(hashlib.sha256(b"appID" + int(app_id).to_bytes(8, "big")).digest())


def key_from_seed(seed_text: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed_text.encode()).digest())


def pub_bytes(sk: Ed25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def verify_sig(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


def txid_of(txn: dict) -> str:
    return b32(hashlib.sha256(b"TX" + canon(txn)).digest())


def group_id_of(txns: list) -> str:
    plain = [{k: v for k, v in t.items() if k != "group"} for t in txns]
    return b32(hashlib.sha256(b"GRP" + b"".join(txid_of(t).encode() for t in plain)).digest())


# ============================================================ قرارداد Lmarket
class ContractError(Exception):
    """رد شدن تراکنش توسط منطق قرارداد (معادل assert/err در TEAL)"""


class Ctx:
    """زمینه‌ی اجرای یک فراخوانی قرارداد"""

    def __init__(self, chain, app, txn, idx, group, ts, rnd):
        self.chain, self.app, self.txn, self.idx, self.group = chain, app, txn, idx, group
        self.sender, self.ts, self.round = txn["sender"], ts, rnd
        self.inner = 0
        self.events = []

    def pay(self, to, amount):
        if amount <= 0:
            return
        self.chain._move(self.app.address, to, amount, app_account=True)
        self.inner += 1

    def emit(self, kind, **data):
        self.events.append({"kind": kind, **data})

    def prev_pay(self):
        """تراکنش پرداخت بلافاصله قبل از این فراخوانی در گروه"""
        if self.idx == 0 or self.group[self.idx - 1]["type"] != "pay":
            raise ContractError("پرداخت همراه فراخوانی در گروه یافت نشد")
        return self.group[self.idx - 1]


def need(cond, msg):
    if not cond:
        raise ContractError(msg)


class LmarketV1:
    """
    قرارداد رسمی سفته‌ی دیجیتال. قواعد (طبق توافق پروژه):
      * بدون مدیر، بدون به‌روزرسانی، بدون ورود/خروج از طرف ثالث.
      * پیش از قفل: هر طرف هر لحظه می‌تواند هر مقدار از واریزی خود را بردارد.
      * همین‌که واریزی هر دو >= مبلغ توافق‌شده شد، دقیقاً همان مبلغ از هر طرف قفل می‌شود
        (قفل شدن در همان تراکنش واریزِ دومی و اتمیک است). مازاد قابل برداشت می‌ماند.
      * تا ثبت هر دو کد تأیید هیچ وثیقه‌ای آزاد نمی‌شود. زمان‌سنج (due) فقط اطلاع‌رسانی است
        و هرگز وثیقه‌ای را آزاد نمی‌کند.
      * کد تأیید = امضای Ed25519 طرف مقابل روی پیامی که به نسخه، زنجیره و شناسه‌ی قرارداد
        گره خورده است؛ پس قابل جعل، حدس یا بازاستفاده در قرارداد دیگر نیست.
    """

    VERSION = "1.0.0"
    UINTS = ["agreed", "due_secs", "dep_b", "dep_s", "locked", "active", "created_at",
             "due_at", "locked_at", "paid_at", "shipped_at", "ent_b", "ent_s", "settled_at"]
    BYTES = ["buyer", "seller", "creator", "version"]
    MIN_AGREED = 100_000            # ۰٫۱ ALGO
    MIN_DUE = 3600                  # یک ساعت
    MAX_DUE = 365 * 86400           # یک سال
    APP_FUND = 100_000              # موجودی پایه‌ی حساب خود قرارداد

    KIND_PAY = "PAYMENT_RECEIVED"   # امضا می‌کند: فروشنده
    KIND_GOODS = "GOODS_RECEIVED"   # امضا می‌کند: خریدار

    @classmethod
    def code_message(cls, version, genesis, app_id, kind) -> bytes:
        return f"LMARKET|{version}|{genesis}|{app_id}|{kind}".encode()

    # ---------------------------------------------------------------- ساخت
    def create(self, c: Ctx, a: dict):
        buyer, seller = a.get("buyer"), a.get("seller")
        need(is_valid_addr(buyer) and is_valid_addr(seller), "آدرس خریدار یا فروشنده نامعتبر است")
        need(buyer != seller, "خریدار و فروشنده نباید یکی باشند")
        need(c.sender in (buyer, seller), "فقط خریدار یا فروشنده می‌تواند قرارداد بسازد")
        agreed, due = a.get("agreed"), a.get("due_secs")
        need(isinstance(agreed, int) and agreed >= self.MIN_AGREED, "وثیقه کمتر از حداقل مجاز است")
        need(isinstance(due, int) and self.MIN_DUE <= due <= self.MAX_DUE, "مهلت خارج از بازه‌ی مجاز است")
        st = {k: 0 for k in self.UINTS}
        st.update(agreed=agreed, due_secs=due, buyer=buyer, seller=seller,
                  creator=c.sender, version=self.VERSION)
        c.app.state = st
        c.emit("created", buyer=buyer, seller=seller, agreed=agreed, due_secs=due)

    def init(self, c: Ctx, a):
        s = c.app.state
        need(c.sender == s["creator"], "فقط سازنده می‌تواند قرارداد را فعال کند")
        need(not s["active"], "قرارداد قبلاً فعال شده است")
        p = c.prev_pay()
        need(p["sender"] == c.sender and p["receiver"] == c.app.address, "گیرنده‌ی پرداخت اشتباه است")
        need(p["amount"] == self.APP_FUND, "مبلغ پایه‌ی حساب قرارداد درست نیست")
        s.update(active=1, created_at=c.ts, due_at=c.ts + s["due_secs"])
        c.emit("activated", due_at=s["due_at"])

    # ---------------------------------------------------------------- واریز/برداشت
    def _party(self, c):
        s = c.app.state
        need(c.sender in (s["buyer"], s["seller"]), "شما طرف این قرارداد نیستید")
        return "b" if c.sender == s["buyer"] else "s"

    def deposit(self, c: Ctx, a):
        s = c.app.state
        who = self._party(c)
        need(s["active"], "قرارداد هنوز فعال نشده است")
        need(not s["settled_at"], "قرارداد تسویه شده است")
        need(not s["locked"], "وثیقه‌ها قفل شده‌اند؛ واریز جدید ممکن نیست")
        p = c.prev_pay()
        need(p["sender"] == c.sender, "فرستنده‌ی پرداخت باید خودِ شما باشد")
        need(p["receiver"] == c.app.address, "گیرنده‌ی پرداخت باید خود قرارداد باشد")
        need(p["amount"] > 0, "مبلغ واریز باید مثبت باشد")
        s["dep_" + who] += p["amount"]
        c.emit("deposit", who=who, amount=p["amount"], dep_b=s["dep_b"], dep_s=s["dep_s"])
        if s["dep_b"] >= s["agreed"] and s["dep_s"] >= s["agreed"]:
            s["locked"], s["locked_at"] = 1, c.ts
            c.emit("locked", agreed=s["agreed"])

    def withdraw(self, c: Ctx, a):
        s = c.app.state
        who = self._party(c)
        amt = a.get("amount")
        need(isinstance(amt, int) and amt > 0, "مبلغ برداشت نامعتبر است")
        need(not s["settled_at"], "قرارداد تسویه شده است")
        free = s["dep_" + who] - (s["agreed"] if s["locked"] else 0)
        need(amt <= free, "بیش از مقدار آزادِ شما (وثیقه‌ی قفل‌شده قابل برداشت نیست)")
        s["dep_" + who] -= amt
        c.pay(c.sender, amt)
        c.emit("withdraw", who=who, amount=amt, locked=bool(s["locked"]))

    # ---------------------------------------------------------------- مراحل معامله
    def mark_shipped(self, c: Ctx, a):
        s = c.app.state
        need(c.sender == s["seller"], "فقط فروشنده می‌تواند ارسال کالا را ثبت کند")
        need(s["locked"] and not s["settled_at"], "وثیقه‌ها هنوز قفل نشده‌اند یا معامله تسویه شده است")
        need(not s["shipped_at"], "ارسال قبلاً ثبت شده است")
        s["shipped_at"] = c.ts
        c.emit("shipped")

    def mark_paid(self, c: Ctx, a):
        s = c.app.state
        need(c.sender == s["buyer"], "فقط خریدار می‌تواند پرداخت را ثبت کند")
        need(s["locked"] and not s["settled_at"], "وثیقه‌ها هنوز قفل نشده‌اند یا معامله تسویه شده است")
        need(not s["paid_at"], "پرداخت قبلاً ثبت شده است")
        s["paid_at"] = c.ts
        c.emit("paid")

    def enter_code(self, c: Ctx, a):
        s = c.app.state
        who = self._party(c)
        need(s["locked"] and not s["settled_at"], "وثیقه‌ها قفل نیستند یا معامله تسویه شده است")
        try:
            sig = unb32(a.get("code", ""))
        except Exception:
            raise ContractError("قالب کد نامعتبر است")
        need(len(sig) == 64, "طول کد نامعتبر است")
        if who == "b":   # خریدار «کد دریافت وجه» فروشنده را وارد می‌کند
            need(s["paid_at"], "ابتدا پرداخت باید ثبت شود")
            need(not s["ent_b"], "این کد قبلاً ثبت شده است")
            signer, kind = s["seller"], self.KIND_PAY
        else:            # فروشنده «کد دریافت کالا» خریدار را وارد می‌کند
            need(s["shipped_at"], "ابتدا ارسال کالا باید ثبت شود")
            need(not s["ent_s"], "این کد قبلاً ثبت شده است")
            signer, kind = s["buyer"], self.KIND_GOODS
        msg = self.code_message(s["version"], c.chain.genesis_id, c.app.id, kind)
        need(verify_sig(pub_from_addr(signer), msg, sig), "کد تأیید معتبر نیست")
        s["ent_" + who] = 1
        c.emit("code_entered", who=who)
        if s["ent_b"] and s["ent_s"]:
            self._settle(c)

    def _settle(self, c):
        s = c.app.state
        b, sl = s["dep_b"], s["dep_s"]
        # دفاع در عمق: اگر موجودی واقعی با دفتر ثبت‌شده نخواند، تسویه انجام نمی‌شود و وضعیت دست نمی‌خورد
        need(c.chain.balance(c.app.address) - self.APP_FUND >= b + sl,
             "موجودی قرارداد با وضعیت ثبت‌شده نمی‌خواند؛ تسویه انجام نشد")
        s["dep_b"] = s["dep_s"] = 0
        s["settled_at"] = c.ts
        c.pay(s["buyer"], b)
        c.pay(s["seller"], sl)
        c.emit("settled", released_b=b, released_s=sl, seconds=c.ts - s["created_at"])

    def delete(self, c: Ctx, a):
        s = c.app.state
        need(c.sender == s["creator"], "فقط سازنده می‌تواند قرارداد را حذف کند")
        # تسویه‌شده، یا رهاشده (فعال‌شده و بدون هیچ واریزی): در هر دو حالت وجوه برمی‌گردد
        abandoned = not s["locked"] and s["dep_b"] == 0 and s["dep_s"] == 0
        need(s["settled_at"] or abandoned,
             "حذف قرارداد فقط پس از تسویه، یا وقتی هیچ واریزی روی آن نیست، ممکن است")
        c.pay(s["creator"], c.chain.accounts[c.app.address]["balance"])
        c.emit("deleted")


class EvilLmarket(LmarketV1):
    """نسخه‌ی مخرب (فقط برای آزمایش): فروشنده می‌تواند وثیقه‌ی قفل‌شده را هم بردارد.
    اگر رابط بررسی امضا/نسخه را درست انجام ندهد، کاربر فریب می‌خورد."""

    def withdraw(self, c: Ctx, a):
        s = c.app.state
        who = self._party(c)
        amt = a.get("amount")
        need(isinstance(amt, int) and amt > 0, "مبلغ برداشت نامعتبر است")
        total = c.chain.accounts[c.app.address]["balance"] - self.APP_FUND
        need(who == "s" or amt <= s["dep_" + who], "رد شد")
        c.pay(c.sender, min(amt, total))
        c.emit("withdraw", who=who, amount=amt, locked=bool(s["locked"]))


def program_hash(cls) -> str:
    return hashlib.sha256(inspect.getsource(cls).encode()).hexdigest()


PROGRAMS = {program_hash(LmarketV1): LmarketV1, program_hash(EvilLmarket): EvilLmarket}
OFFICIAL_HASH = program_hash(LmarketV1)
EVIL_HASH = program_hash(EvilLmarket)

METHODS = {"create", "init", "deposit", "withdraw", "mark_shipped", "mark_paid",
           "enter_code", "delete"}


def app_min_balance() -> int:
    n_u, n_b = len(LmarketV1.UINTS), len(LmarketV1.BYTES)
    return 100_000 + n_u * (25_000 + 3_500) + n_b * (25_000 + 25_000)


# ============================================================ انتشار و امضای ناشر
def publisher_key() -> Ed25519PrivateKey:
    """کلید ناشر از فایل خارج از وب خوانده می‌شود؛ اگر نباشد یک بار ساخته می‌شود."""
    path = SETTINGS["PUBLISHER_KEY_FILE"]
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(json.load(f)["private"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sk = Ed25519PrivateKey.generate()
    raw = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"private": raw.hex()}, f)
    os.chmod(path, 0o600)
    return sk


def publisher_pub_hex() -> str:
    return pub_bytes(publisher_key()).hex()


def release_message(version: str, approval_hash: str) -> bytes:
    return f"LMARKET-RELEASE|{version}|{approval_hash}".encode()


def release_manifest() -> dict:
    sig = publisher_key().sign(release_message(LmarketV1.VERSION, OFFICIAL_HASH))
    return {
        "publisher": publisher_pub_hex(),
        "releases": [{"version": LmarketV1.VERSION, "approval_hash": OFFICIAL_HASH,
                      "sig": sig.hex()}],
    }


def verify_release(manifest: dict, version: str, approval_hash: str) -> bool:
    """معادل کاری که رابط HTML باید انجام دهد؛ publisher باید از بیرون (کلید ثابت در رابط) بیاید."""
    pub = bytes.fromhex(manifest["publisher"])
    for r in manifest["releases"]:
        if r["version"] == version and r["approval_hash"] == approval_hash:
            return verify_sig(pub, release_message(version, approval_hash), bytes.fromhex(r["sig"]))
    return False


# ============================================================ زنجیره
class App:
    def __init__(self, app_id, creator, approval_hash, rnd, ts):
        self.id, self.creator, self.approval_hash = app_id, creator, approval_hash
        self.address = app_address(app_id)
        self.state = {}
        self.created_round, self.created_ts = rnd, ts


class SubmitError(Exception):
    pass


class Chain:
    def __init__(self, clock=time.time):
        # هر دنیای تازه شناسه‌ی زنجیره‌ی خودش را دارد؛ کد یک دنیای قدیمی در دنیای دیگر معتبر نیست
        self.genesis_id = f'{SETTINGS["GENESIS_ID"]}-{secrets.token_hex(4)}'
        self.clock, self.offset = clock, 0.0
        self.round, self.ts = 1, int(clock())
        self.accounts, self.apps = {}, {}
        self.next_app_id = 1001
        self.fee_sink = 0
        self.clog = {}           # سابقه‌ی همه‌ی قراردادها (ایندکسر؛ پس از حذف هم می‌ماند)
        self.events = []
        self.pool, self.groups = [], {}
        self.seen = set()
        self.faults = {"offline": False, "paused": False, "drop_next": 0, "latency_ms": 0}
        self.lock = threading.RLock()
        self.total_supply = 0
        self.dispenser = key_from_seed(SETTINGS["DISPENSER_SEED"])
        self.dispenser_addr = addr_from_pub(pub_bytes(self.dispenser))
        self._credit(self.dispenser_addr, 10_000_000 * ALGO, first_ts=self.ts)

    # ------------------------------------------------ حساب‌ها
    def now(self):
        return int(self.clock() + self.offset)

    def _acct(self, addr):
        return self.accounts.setdefault(addr, {"balance": 0, "first_ts": None, "first_round": None})

    def _credit(self, addr, amount, first_ts=None):
        a = self._acct(addr)
        a["balance"] += amount
        self.total_supply += amount
        if a["first_ts"] is None:
            a["first_ts"] = first_ts if first_ts is not None else self.ts
            a["first_round"] = self.round

    def min_balance(self, addr):
        if addr in {x.address for x in self.apps.values()}:
            return SETTINGS["ACCOUNT_MIN_BALANCE"]
        extra = sum(app_min_balance() for x in self.apps.values() if x.creator == addr)
        return SETTINGS["ACCOUNT_MIN_BALANCE"] + extra

    def balance(self, addr):
        return self.accounts.get(addr, {}).get("balance", 0)

    def _check_min(self, addr):
        b = self.balance(addr)
        if b != 0 and b < self.min_balance(addr):
            raise ContractError(
                f"موجودی حساب {addr[:6]}… از حداقل مجاز ({self.min_balance(addr)} microAlgo) کمتر می‌شود")

    def _move(self, src, dst, amount, app_account=False):
        if amount < 0:
            raise ContractError("مبلغ منفی")
        if self.balance(src) < amount:
            raise ContractError("موجودی کافی نیست")
        self._acct(src)["balance"] -= amount
        self._credit_no_supply(dst, amount)
        self._check_min(src)
        self._check_min(dst)

    def _credit_no_supply(self, addr, amount):
        a = self._acct(addr)
        a["balance"] += amount
        if a["first_ts"] is None:
            a["first_ts"], a["first_round"] = self.ts, self.round

    def fund(self, addr, amount, first_ts=None):
        """اعتباردهی مستقیم (فقط برای ساخت دنیای دمو؛ معادل Faucet)"""
        with self.lock:
            self._acct(self.dispenser_addr)["balance"] -= amount
            a = self._acct(addr)
            a["balance"] += amount
            if a["first_ts"] is None:
                a["first_ts"] = first_ts if first_ts is not None else self.ts
                a["first_round"] = self.round

    # ------------------------------------------------ زمان و بلوک
    def produce_block(self):
        with self.lock:
            if self.faults["paused"]:
                return None
            self.round += 1
            self.ts = max(self.ts, self.now())
            pool, self.pool = self.pool, []
            for g in pool:
                rec = self.groups[g["gid"]]
                if self.round > g["last_valid"]:
                    rec.update(status="expired", error="بازه‌ی اعتبار تراکنش تمام شد")
                    continue
                if self.round < g["first_valid"]:
                    self.pool.append(g)
                    continue
                snap = self._snapshot()
                try:
                    evs, inner = self._apply_group(g["txns"], self.ts, self.round)
                    rec.update(status="confirmed", round=self.round, ts=self.ts)
                    for e in evs:
                        e.update(round=self.round, ts=self.ts, gid=g["gid"])
                        self.events.append(e)
                except ContractError as ex:
                    self._restore(snap)
                    rec.update(status="rejected", error=str(ex), round=self.round)
            return self.round

    def advance(self, seconds):
        """پیشروی ساعت زنجیره (برای آزمودن تایمر)؛ راندها هم متناسب جلو می‌روند"""
        with self.lock:
            self.offset += seconds
            self.round += max(0, int(seconds / SETTINGS["BLOCK_TIME"]) - 1)
            self.ts = max(self.ts, self.now())
            return self.produce_block()

    # ------------------------------------------------ ارسال تراکنش
    def submit(self, signed_group):
        with self.lock:
            if self.faults["offline"]:
                raise SubmitError("گره در دسترس نیست")
            txns = [s["txn"] for s in signed_group]
            if not 1 <= len(txns) <= SETTINGS["MAX_GROUP"]:
                raise SubmitError("اندازه‌ی گروه نامعتبر است")
            for s in signed_group:
                t = s["txn"]
                try:
                    sig = bytes.fromhex(s["sig"])
                    ok = verify_sig(pub_from_addr(t["sender"]), b"TX" + canon(t), sig)
                except Exception:
                    ok = False
                if not ok:
                    raise SubmitError("امضای تراکنش معتبر نیست")
                if t.get("genesis") != self.genesis_id:
                    raise SubmitError("تراکنش برای زنجیره‌ی دیگری است")
                if not (0 <= t["fee"] and t["first_valid"] <= t["last_valid"] <= t["first_valid"] + SETTINGS["TX_VALIDITY"]):
                    raise SubmitError("بازه‌ی اعتبار تراکنش نامعتبر است")
                if self.round + 1 > t["last_valid"]:
                    raise SubmitError("تراکنش منقضی شده است")
            if len(txns) > 1:
                gid = group_id_of(txns)
                if any(t.get("group") != gid for t in txns):
                    raise SubmitError("شناسه‌ی گروه ناسازگار است")
            else:
                gid = txid_of(txns[0])
            ids = [txid_of(t) for t in txns]
            if gid in self.groups or any(i in self.seen for i in ids):
                raise SubmitError("تراکنش تکراری است (replay)")
            snap = self._snapshot()
            try:
                self._apply_group(txns, self.ts, self.round + 1)
            except ContractError as ex:
                raise SubmitError(str(ex))
            finally:
                self._restore(snap)
            self.seen.update(ids)
            last_valid = min(t["last_valid"] for t in txns)
            first_valid = max(t["first_valid"] for t in txns)
            rec = {"status": "pending", "last_valid": last_valid, "txids": ids}
            self.groups[gid] = rec
            if self.faults["drop_next"] > 0:
                self.faults["drop_next"] -= 1
                rec["dropped"] = True
            else:
                self.pool.append({"gid": gid, "txns": txns, "last_valid": last_valid, "first_valid": first_valid})
            return gid

    def tx_status(self, gid):
        with self.lock:
            rec = self.groups.get(gid)
            if not rec:
                return {"status": "unknown"}
            out = {k: v for k, v in rec.items() if k != "txids"}
            for e in self.events:
                if e.get("gid") == gid and e["kind"] == "created":
                    out["app_id"] = e["app_id"]
            if out["status"] == "pending" and self.round > rec["last_valid"]:
                out.update(status="expired", error="بازه‌ی اعتبار تراکنش تمام شد (احتمالاً به شبکه نرسید)")
            return out

    def _snapshot(self):
        return (copy.deepcopy(self.accounts), copy.deepcopy(self.apps), copy.deepcopy(self.clog),
                self.next_app_id, self.fee_sink)

    def _restore(self, s):
        self.accounts, self.apps, self.clog, self.next_app_id, self.fee_sink = s

    # ------------------------------------------------ اجرای گروه
    def _apply_group(self, txns, ts, rnd):
        events, inner_total, fees = [], 0, 0
        for i, t in enumerate(txns):
            fees += t["fee"]
            self._take_fee(t)
            if t["type"] == "pay":
                need(isinstance(t["amount"], int) and t["amount"] >= 0, "مبلغ نامعتبر")
                need(is_valid_addr(t["receiver"]), "آدرس گیرنده نامعتبر است")
                self._move(t["sender"], t["receiver"], t["amount"])
            elif t["type"] == "appl":
                inner_total += self._apply_appl(t, i, txns, ts, rnd, events)
            else:
                raise ContractError("نوع تراکنش ناشناخته")
            self._check_min(t["sender"])
        need(fees >= MIN_FEE * (len(txns) + inner_total),
             f"کارمزد کافی نیست: حداقل {MIN_FEE * (len(txns) + inner_total)} microAlgo لازم است")
        return events, inner_total

    def _take_fee(self, t):
        need(self.balance(t["sender"]) >= t["fee"], "موجودی برای پرداخت کارمزد کافی نیست")
        self._acct(t["sender"])["balance"] -= t["fee"]
        self.fee_sink += t["fee"]

    def _apply_appl(self, t, idx, group, ts, rnd, events):
        method, delete = t.get("method"), t.get("on_complete") == "delete"
        need(method in METHODS, "متد ناشناخته")
        need(t.get("on_complete", "noop") in ("noop", "delete"), "نوع on_complete مجاز نیست")
        need(delete == (method == "delete"), "on_complete با متد سازگار نیست")
        if t["app_id"] == 0:
            need(method == "create", "ابتدا باید قرارداد ساخته شود")
            h = t.get("approval_hash")
            need(h in PROGRAMS, "برنامه‌ی قرارداد ناشناخته است")
            app = App(self.next_app_id, t["sender"], h, rnd, ts)
            self.next_app_id += 1
            self.apps[app.id] = app
            self._acct(app.address)
        else:
            need(t["app_id"] in self.apps, "قرارداد وجود ندارد (یا حذف شده است)")
            app = self.apps[t["app_id"]]
            need(method != "create", "قرارداد قبلاً ساخته شده است")
        ctx = Ctx(self, app, t, idx, group, ts, rnd)
        cls = PROGRAMS[app.approval_hash]
        getattr(cls(), method)(ctx, t.get("args") or {})
        s = app.state
        if method == "create":
            self.clog[app.id] = {"app_id": app.id, "buyer": s["buyer"], "seller": s["seller"],
                                 "agreed": s["agreed"], "created_at": None, "due_at": None,
                                 "settled_at": None, "active": False, "hash": app.approval_hash}
        c = self.clog.get(app.id)
        if c and method == "deposit":
            c.setdefault("funded", [])
            if t["sender"] not in c["funded"]:
                c["funded"].append(t["sender"])
        if c:
            c.update(created_at=s.get("created_at") or None, due_at=s.get("due_at") or None,
                     settled_at=s.get("settled_at") or None, active=bool(s.get("active")))
        for e in ctx.events:
            events.append({"app_id": app.id, "sender": t["sender"], "txid": txid_of(t), **e})
        if delete:
            del self.apps[app.id]
            self.clog[app.id]["deleted"] = True
        return ctx.inner

    # ------------------------------------------------ خواندن (algod/ایندکسر)
    def params(self):
        with self.lock:
            return {"round": self.round, "ts": self.ts, "now": self.now(), "genesis": self.genesis_id,
                    "min_fee": MIN_FEE, "app_min_balance": app_min_balance(),
                    "app_fund": LmarketV1.APP_FUND, "min_agreed": LmarketV1.MIN_AGREED,
                    "min_due": LmarketV1.MIN_DUE, "max_due": LmarketV1.MAX_DUE,
                    "official_hash": OFFICIAL_HASH, "version": LmarketV1.VERSION,
                    "evil_hash": EVIL_HASH,   # فقط در شبیه‌ساز: برای آزمودن بررسی امضا
                    "faults": dict(self.faults), "pool": len(self.pool)}

    def account_info(self, addr):
        with self.lock:
            a = self.accounts.get(addr)
            return {"address": addr, "valid": is_valid_addr(addr), "balance": self.balance(addr),
                    "min_balance": self.min_balance(addr),
                    "first_ts": a["first_ts"] if a else None, "exists": bool(a)}

    def app_info(self, app_id):
        with self.lock:
            app = self.apps.get(app_id)
            if not app:
                c = self.clog.get(app_id)
                return {"id": app_id, "exists": False, "deleted": bool(c and c.get("deleted"))}
            s = dict(app.state)
            return {"id": app.id, "exists": True, "address": app.address, "creator": app.creator,
                    "approval_hash": app.approval_hash, "state": s,
                    "balance": self.balance(app.address), "created_round": app.created_round,
                    "round": self.round, "ts": self.ts, "now": self.now()}

    def apps_for(self, addr):
        """فهرست قراردادهای یک آدرس (ایندکسر)؛ قراردادهای دموی تاریخی را شامل نمی‌شود"""
        with self.lock:
            out = []
            for c in self.clog.values():
                if c.get("seeded") or addr not in (c["buyer"], c["seller"]):
                    continue
                live = self.apps.get(c["app_id"])
                st = live.state if live else {}
                out.append({"app_id": c["app_id"], "role": "buyer" if addr == c["buyer"] else "seller",
                            "agreed": c["agreed"], "active": c["active"], "locked": bool(st.get("locked")),
                            "settled": bool(c["settled_at"]), "deleted": bool(c.get("deleted")),
                            "due_at": c["due_at"]})
            return sorted(out, key=lambda x: -x["app_id"])

    def events_for(self, app_id):
        with self.lock:
            return [e for e in self.events if e["app_id"] == app_id]

    def reputation(self, addr):
        with self.lock:
            now = self.now()
            a = self.accounts.get(addr)
            # فقط قراردادهایی که این آدرس واقعاً در آن واریز کرده، حساب می‌شوند (جلوی جعل اعتبار)
            mine = [c for c in self.clog.values() if addr in c.get("funded", []) and c["active"]]
            settled = [c for c in mine if c["settled_at"]]
            open_ = [c for c in mine if not c["settled_at"] and not c.get("deleted")]
            overdue = [c for c in open_ if c["due_at"] and now > c["due_at"]]
            durs = [c["settled_at"] - c["created_at"] for c in settled if c["created_at"]]
            return {
                "address": addr, "valid": is_valid_addr(addr),
                "wallet_age_days": int((now - a["first_ts"]) / 86400) if a and a["first_ts"] else None,
                "total": len(mine), "settled": len(settled), "open": len(open_),
                "overdue_open": len(overdue),
                "avg_settle_hours": round(sum(durs) / len(durs) / 3600, 1) if durs else None,
                "oldest_open_days": round(max((now - c["created_at"]) for c in open_) / 86400, 1) if open_ else 0,
            }

    # ------------------------------------------------ تزریق خطا
    def set_fault(self, **kw):
        with self.lock:
            for k, v in kw.items():
                if k in self.faults:
                    self.faults[k] = v

    def supply_check(self):
        """ثابت‌ماندن مجموع پول: موجودی‌ها + کارمزدها == عرضه‌ی اولیه"""
        with self.lock:
            return sum(a["balance"] for a in self.accounts.values()) + self.fee_sink


# ============================================================ کیف پول شبیه‌سازی‌شده
class Wallet:
    def __init__(self, name, seed=None):
        self.name = name
        self.sk = key_from_seed(seed or f"lmarket-wallet-{name}")
        self.address = addr_from_pub(pub_bytes(self.sk))

    def sign_txn(self, txn):
        return {"txn": txn, "sig": self.sk.sign(b"TX" + canon(txn)).hex()}

    def sign_message(self, msg: bytes) -> bytes:
        return self.sk.sign(msg)


def build_group(chain: Chain, sender: str, intent: dict):
    """از «قصد کاربر» گروه تراکنش بدون امضا + خلاصه برای پنجره‌ی تأیید کیف پول می‌سازد"""
    p = chain.params()
    kind = intent["kind"]
    app_id = int(intent.get("app_id") or 0)
    addr = app_address(app_id) if app_id else None

    def base(**kw):
        t = {"sender": sender, "fee": MIN_FEE, "first_valid": p["round"], "genesis": chain.genesis_id,
             "last_valid": p["round"] + 500}
        t.update(kw)
        return t

    def call(method, args=None, fee=MIN_FEE, oc="noop"):
        return base(type="appl", app_id=app_id, method=method, args=args or {}, fee=fee, on_complete=oc)

    pay_out, notes, txns = 0, [], []
    if kind == "create":
        txns = [call("create", {"buyer": intent["buyer"], "seller": intent["seller"],
                                "agreed": int(intent["agreed"]), "due_secs": int(intent["due_secs"])})]
        txns[0]["approval_hash"] = intent.get("approval_hash", OFFICIAL_HASH)
        notes = ["reserve", "create"]
    elif kind == "init":
        txns = [base(type="pay", receiver=addr, amount=LmarketV1.APP_FUND), call("init")]
        pay_out = LmarketV1.APP_FUND
    elif kind == "deposit":
        amt = int(intent["amount"])
        txns = [base(type="pay", receiver=addr, amount=amt), call("deposit")]
        pay_out = amt
    elif kind == "withdraw":
        txns = [call("withdraw", {"amount": int(intent["amount"])}, fee=2 * MIN_FEE)]
    elif kind in ("mark_paid", "mark_shipped"):
        txns = [call(kind)]
    elif kind == "enter_code":
        txns = [call("enter_code", {"code": intent["code"]}, fee=3 * MIN_FEE)]
    elif kind == "delete":
        txns = [call("delete", fee=2 * MIN_FEE, oc="delete")]
    else:
        raise ValueError("قصد ناشناخته")
    if len(txns) > 1:
        gid = group_id_of(txns)
        for t in txns:
            t["group"] = gid
    summary = {"kind": kind, "app_id": app_id, "pay_out": pay_out, "fee": sum(t["fee"] for t in txns),
               "txn_count": len(txns), "notes": notes}
    return txns, summary


def code_for(wallet: Wallet, chain: Chain, app_info: dict, kind: str) -> str:
    """کد تأیید = امضای Ed25519 کیف پول؛ قطعی است، پس با امضای دوباره قابل بازیابی است"""
    msg = LmarketV1.code_message(app_info["state"]["version"], chain.genesis_id, app_info["id"], kind)
    return b32(wallet.sign_message(msg))


# ============================================================ دنیای دمو
DEMO_PEOPLE = {   # نام: سن کیف پول (روز)
    "Alice": 800, "Bob": 200, "Carol": 40, "Mallory": 0, "Dave": 120,
}


def make_demo_world(clock=time.time):
    chain = Chain(clock)
    wallets = {n: Wallet(n) for n in DEMO_PEOPLE}
    for n, age in DEMO_PEOPLE.items():
        chain.fund(wallets[n].address, 1000 * ALGO, first_ts=chain.ts - age * 86400)
    now = chain.ts

    def hist(buyer, seller, n_settled, avg_h, n_open=0, overdue=0):
        i = 0
        for k in range(n_settled):
            i += 1
            created = now - (200 - k * 9) * 86400
            chain.clog[-(len(chain.clog) + 1)] = {
                "app_id": -i, "buyer": buyer, "seller": seller, "agreed": 5 * ALGO,
                "created_at": created, "due_at": created + 7 * 86400,
                "settled_at": created + int(avg_h * 3600), "active": True, "hash": OFFICIAL_HASH,
                "seeded": True, "funded": [buyer, seller]}
        for k in range(n_open):
            created = now - (100 - k * 3) * 86400
            due = created + 7 * 86400 if k < overdue else now + 5 * 86400
            chain.clog[-(len(chain.clog) + 1)] = {
                "app_id": -(100 + k), "buyer": buyer, "seller": seller, "agreed": 5 * ALGO,
                "created_at": created, "due_at": due, "settled_at": None, "active": True,
                "hash": OFFICIAL_HASH, "seeded": True, "funded": [buyer, seller]}

    other = wallets["Carol"].address
    hist(other, wallets["Alice"].address, 14, 60)                    # Alice: سابقه‌ی درخشان
    hist(other, wallets["Bob"].address, 5, 90, n_open=1)             # Bob: معمولی
    hist(wallets["Bob"].address, wallets["Carol"].address, 3, 120)   # Carol: تازه‌کار
    hist(other, wallets["Dave"].address, 2, 800, n_open=20, overdue=18)  # Dave: بیست قرارداد باز، بیشترشان عقب‌افتاده
    return chain, wallets


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "release":
        print(json.dumps(release_manifest(), indent=2))
    else:
        print("official hash:", OFFICIAL_HASH)
        print("app min balance (microAlgo):", app_min_balance())
        print("publisher:", publisher_pub_hex())
