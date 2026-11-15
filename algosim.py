"""
algosim.py - local Algorand-style simulator for the Lmarket escrow contract.

Contains: deterministic in-memory chain (accounts, fees, atomic groups, blocks,
expiry, faults), Lmarket v1 contract rules, Ed25519 wallets, confirmation codes,
and a signed release manifest. No network, no real money.
Only dependency: the `cryptography` package.
"""
import base64
import copy
import hashlib
import json
import os
import time
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# ----------------------------------------------------------------- constants
ALGO = 1_000_000                 # micro-ALGO per ALGO
MIN_FEE = 1_000                  # micro-ALGO per transaction
BASE_MIN = 100_000               # minimum balance of any account / contract account
APP_MIN = 100_000                # extra reserve per live contract owned by its creator
APP_FUND = 100_000               # base balance the creator pays into a contract at init
MIN_AGREED = 100_000             # smallest collateral per side
DAY = 86_400
MIN_DUE = DAY
MAX_DUE = 365 * DAY
VALID_ROUNDS = 1_000             # transaction validity window in rounds
VERSION = "1.0.0"
TOTAL_SUPPLY = 10_000_000 * ALGO
FIRST_APP_ID = 1001
SETTINGS = {"BLOCK_TIME": 3}     # seconds per round

OFFICIAL_HASH = hashlib.sha256(b"lmarket approval program 1.0.0 official").hexdigest()
EVIL_HASH = hashlib.sha256(b"lmarket approval program 1.0.0 tampered").hexdigest()
KNOWN_HASHES = (OFFICIAL_HASH, EVIL_HASH)

_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publisher_key.json")


class SubmitError(Exception):
    """A rejected transaction. The message is shown to the user."""


# ----------------------------------------------------------------- encoding
def b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode().rstrip("=")


def _checksum(pk: bytes) -> bytes:
    return hashlib.new("sha512_256", pk).digest()[-4:]


def encode_address(pk: bytes) -> str:
    return b32(pk + _checksum(pk))


def decode_address(addr) -> bytes:
    if not isinstance(addr, str) or len(addr) != 58:
        raise ValueError("bad address length")
    raw = base64.b32decode(addr + "=" * 6)
    pk, ck = raw[:32], raw[32:]
    if len(raw) != 36 or _checksum(pk) != ck:
        raise ValueError("bad address checksum")
    return pk


def app_address(app_id) -> str:
    return encode_address(hashlib.sha256(b"lmarket-app:" + str(app_id).encode()).digest())


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _without_group(t):
    return {k: v for k, v in t.items() if k != "group"}


def group_id_of(txns) -> str:
    return b32(hashlib.sha256(b"TG" + _canon([_without_group(t) for t in txns])).digest())


def _txid(signed) -> str:
    return b32(hashlib.sha256(b"TX" + _canon(signed)).digest())


# ----------------------------------------------------------------- wallets
class Wallet:
    """Deterministic demo wallet: the key is derived from the name."""

    def __init__(self, name: str):
        self.name = name
        seed = hashlib.sha256(b"lmarket-wallet:" + name.encode()).digest()
        self._sk = Ed25519PrivateKey.from_private_bytes(seed)
        self.pk = self._sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.address = encode_address(self.pk)

    def sign_message(self, msg: bytes) -> bytes:
        return self._sk.sign(msg)

    def sign_txn(self, txn) -> dict:
        t = json.loads(json.dumps(txn))
        return {"txn": t, "sig": self._sk.sign(_canon(t)).hex()}


# ----------------------------------------------------------------- release signature
@lru_cache(maxsize=None)
def _publisher():
    """Publisher key lives in publisher_key.json next to this file. Keep it out of git."""
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, encoding="utf-8") as f:
            sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(json.load(f)["private"]))
    else:
        sk = Ed25519PrivateKey.generate()
        raw = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                               serialization.NoEncryption())
        with open(_KEY_FILE, "w", encoding="utf-8") as f:
            json.dump({"private": raw.hex()}, f)
        os.chmod(_KEY_FILE, 0o600)
        pub_hex = sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        print("Created publisher key. Set CONFIG.publisher in index.html to:")
        print(pub_hex)
    pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sk, pub


def _release_msg(version, approval_hash) -> bytes:
    return f"LMARKET-RELEASE|{version}|{approval_hash}".encode()


def release_manifest() -> dict:
    sk, pub = _publisher()
    return {
        "publisher": pub.hex(),
        "releases": [{
            "version": VERSION,
            "approval_hash": OFFICIAL_HASH,
            "sig": sk.sign(_release_msg(VERSION, OFFICIAL_HASH)).hex(),
        }],
    }


def verify_release(manifest, version, approval_hash) -> bool:
    try:
        _, trusted = _publisher()
        if manifest["publisher"] != trusted.hex():
            return False
        pub = Ed25519PublicKey.from_public_bytes(trusted)
        for r in manifest["releases"]:
            if r["version"] == version and r["approval_hash"] == approval_hash:
                pub.verify(bytes.fromhex(r["sig"]), _release_msg(version, approval_hash))
                return True
    except (InvalidSignature, KeyError, ValueError, TypeError):
        pass
    return False


# ----------------------------------------------------------------- contract helpers
class LmarketV1:
    VERSION = VERSION
    APP_FUND = APP_FUND
    KIND_PAY = "PAYMENT_RECEIVED"    # seller confirms payment received
    KIND_GOODS = "GOODS_RECEIVED"    # buyer confirms goods received

    @staticmethod
    def code_message(version, genesis_id, app_id, kind) -> bytes:
        return f"LMARKET|{version}|{genesis_id}|{app_id}|{kind}".encode()


def code_for(wallet, chain, info, kind) -> str:
    """Confirmation code = base32 of the wallet's Ed25519 signature (103 chars)."""
    msg = LmarketV1.code_message(info["state"]["version"], chain.genesis_id, info["id"], kind)
    return b32(wallet.sign_message(msg))


def app_min_balance() -> int:
    return APP_MIN


def build_group(chain, sender, intent):
    """Return (unsigned txns, summary). Does not validate state; submit() does."""
    kind = intent.get("kind")
    rnd = chain.round
    base = {"sender": sender, "fee": MIN_FEE, "first_valid": rnd,
            "last_valid": rnd + VALID_ROUNDS, "genesis": chain.genesis_id}

    def appl(op, app_id, args=None, fee=MIN_FEE):
        return {**base, "fee": fee, "type": "appl", "op": op, "app_id": app_id, "args": args or {}}

    def pay(receiver, amount):
        return {**base, "type": "pay", "receiver": receiver, "amount": amount}

    app_id = intent.get("app_id")
    if kind == "create":
        args = {"buyer": intent.get("buyer"), "seller": intent.get("seller"),
                "agreed": intent.get("agreed"), "due_secs": intent.get("due_secs"),
                "approval_hash": intent.get("approval_hash", OFFICIAL_HASH)}
        txns = [appl("create", None, args)]
    elif kind == "init":
        txns = [pay(app_address(app_id), APP_FUND), appl("init", app_id)]
    elif kind == "deposit":
        amt = intent.get("amount")
        txns = [pay(app_address(app_id), amt), appl("deposit", app_id, {"amount": amt})]
    elif kind == "withdraw":
        txns = [appl("withdraw", app_id, {"amount": intent.get("amount")}, fee=2 * MIN_FEE)]
    elif kind == "delete":
        txns = [appl("delete", app_id, fee=2 * MIN_FEE)]
    elif kind in ("mark_paid", "mark_shipped"):
        txns = [appl(kind, app_id)]
    elif kind == "enter_code":
        txns = [appl("enter_code", app_id, {"code": intent.get("code")})]
    else:
        raise ValueError(f"unknown intent: {kind}")

    if len(txns) > 1:
        g = group_id_of(txns)
        for t in txns:
            t["group"] = g

    summary = {
        "kind": kind,
        "app_id": app_id if kind != "create" else None,
        "pay_out": sum(t["amount"] for t in txns if t["type"] == "pay"),
        "fee": sum(t["fee"] for t in txns),
    }
    return txns, summary


# ----------------------------------------------------------------- ledger helpers
def _min_of(L, addr) -> int:
    if addr in (L["dispenser"], L["fee_sink"]):
        return 0
    if addr in L["app_addrs"]:
        return BASE_MIN
    owned = sum(1 for a in L["apps"].values() if a["creator"] == addr and a["exists"])
    return BASE_MIN + APP_MIN * owned


def _check_min(L, addr):
    bal = L["balances"].get(addr, 0)
    if bal and bal < _min_of(L, addr):
        raise SubmitError("این عملیات موجودی حساب را زیر حداقل مجاز می‌برد (حداقل موجودی حساب)")


def _transfer(L, c, src, dst, amt):
    if not isinstance(amt, int) or amt <= 0:
        raise SubmitError("مبلغ باید عدد صحیح مثبت باشد")
    if L["balances"].get(src, 0) < amt:
        raise SubmitError("موجودی کافی نیست")
    L["balances"][src] -= amt
    L["balances"][dst] = L["balances"].get(dst, 0) + amt
    L["first_seen"].setdefault(dst, c["now"])
    c["touched"].update((src, dst))


def _event(L, c, app_id, kind, **kw):
    L["events"].setdefault(app_id, []).append(
        {"kind": kind, "ts": c["now"], "round": c["rnd"], "txid": c["gid"], **kw})


def _get_app(L, app_id):
    a = L["apps"].get(app_id)
    if a is None or not a["exists"]:
        raise SubmitError("قرارداد وجود ندارد یا حذف شده است")
    return a


def _role(a, addr):
    if addr == a["buyer"]:
        return "buyer"
    if addr == a["seller"]:
        return "seller"
    return None


_STATE_KEYS = ("version", "creator", "buyer", "seller", "agreed", "due_secs", "created_at",
               "due_at", "active", "locked", "dep_b", "dep_s", "paid_at", "shipped_at",
               "ent_b", "ent_s", "settled_at")


# ----------------------------------------------------------------- chain
class Chain:
    def __init__(self, clock=None):
        self._clock = clock or time.time
        self.offset = 0
        self.genesis_id = "lmarket-sim-v1"
        self.total_supply = TOTAL_SUPPLY
        self.round = 1_000
        self.faults = {"offline": False, "paused": False, "drop_next": 0, "latency_ms": 0}
        self.pool = []           # pending groups, processed in order
        self.txs = {}            # gid -> status record
        disp = Wallet("__dispenser__").address
        fee = Wallet("__fee_sink__").address
        self.L = {
            "dispenser": disp,
            "fee_sink": fee,
            "balances": {disp: TOTAL_SUPPLY},
            "first_seen": {disp: 0},
            "apps": {},
            "events": {},
            "app_addrs": {},
            "next_app_id": FIRST_APP_ID,
        }

    # ---- read-only properties
    @property
    def dispenser_addr(self):
        return self.L["dispenser"]

    @property
    def next_app_id(self):
        return self.L["next_app_id"]

    @property
    def accounts(self):
        return list(self.L["balances"])

    def now(self) -> int:
        return int(self._clock()) + self.offset

    def balance(self, addr) -> int:
        return self.L["balances"].get(addr, 0)

    def min_balance(self, addr) -> int:
        return _min_of(self.L, addr)

    def supply_check(self) -> int:
        return sum(self.L["balances"].values())

    def params(self):
        return {"now": self.now(), "round": self.round, "genesis": self.genesis_id,
                "block_time": SETTINGS["BLOCK_TIME"], "app_fund": APP_FUND,
                "app_min_balance": APP_MIN, "min_agreed": MIN_AGREED,
                "evil_hash": EVIL_HASH, "total_supply": TOTAL_SUPPLY,
                "faults": dict(self.faults)}

    def account_info(self, addr):
        return {"address": addr, "balance": self.balance(addr), "min_balance": self.min_balance(addr)}

    def reputation(self, addr):
        try:
            decode_address(addr)
        except ValueError:
            return {"valid": False, "address": addr}
        now = self.now()
        seen = self.L["first_seen"].get(addr)
        rel = [a for a in self.L["apps"].values()
               if a["active"] and addr in (a["buyer"], a["seller"])]
        settled = [a for a in rel if a["settled_at"]]
        open_ = [a for a in rel if not a["settled_at"] and a["exists"]]
        overdue = [a for a in open_ if now > a["due_at"]]
        avg = None
        if settled:
            avg = round(sum(a["settled_at"] - a["created_at"] for a in settled) / len(settled) / 3600, 1)
        return {
            "valid": True, "address": addr,
            "wallet_age_days": None if seen is None else (now - seen) // DAY,
            "total": len(rel), "settled": len(settled), "open": len(open_),
            "overdue_open": len(overdue), "avg_settle_hours": avg,
            "oldest_open_days": max(((now - a["created_at"]) // DAY for a in open_), default=0),
        }

    def app_info(self, app_id):
        app_id = int(app_id)
        a = self.L["apps"].get(app_id)
        if a is None:
            return {"id": app_id, "exists": False, "deleted": False}
        return {"id": a["id"], "exists": a["exists"], "deleted": not a["exists"],
                "address": a["address"], "balance": self.balance(a["address"]),
                "approval_hash": a["approval_hash"],
                "state": {k: a[k] for k in _STATE_KEYS}}

    def events_for(self, app_id):
        return list(self.L["events"].get(int(app_id), []))

    def apps_for(self, addr):
        out = []
        for a in self.L["apps"].values():
            role = _role(a, addr)
            if role is None:
                continue
            out.append({"app_id": a["id"], "role": role, "agreed": a["agreed"],
                        "active": bool(a["active"]), "locked": bool(a["locked"]),
                        "settled": bool(a["settled_at"]), "deleted": not a["exists"]})
        return out

    def tx_status(self, gid):
        rec = self.txs.get(gid)
        if rec is None:
            return {"gid": gid, "status": "unknown", "round": None,
                    "error": "تراکنشی با این شناسه پیدا نشد"}
        status, err = rec["status"], rec["error"]
        if status == "pending" and self.round > rec["last_valid"]:
            status, err = "expired", "تراکنش منقضی شد و در بلاکی نیامد"
        return {"gid": gid, "status": status, "round": rec["round"], "error": err}

    # ---- state transition
    def _exec(self, L, signed, gid, rnd, now):
        c = {"rnd": rnd, "now": now, "gid": gid, "touched": set()}
        try:
            self._exec_checked(L, c, signed)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as ex:
            raise SubmitError("درخواست ناقص یا نادرست است") from ex

    def _exec_checked(self, L, c, signed):
        if not signed:
            raise SubmitError("تراکنشی ارسال نشده است")
        txns = []
        for s in signed:
            t = s["txn"]
            try:
                pk = decode_address(t["sender"])
                Ed25519PublicKey.from_public_bytes(pk).verify(bytes.fromhex(s["sig"]), _canon(t))
            except (InvalidSignature, ValueError, KeyError, TypeError):
                raise SubmitError("امضای تراکنش نامعتبر است") from None
            if t.get("genesis") != self.genesis_id:
                raise SubmitError("شبکه‌ی تراکنش با این زنجیره نمی‌خواند")
            if not t["first_valid"] <= c["rnd"] <= t["last_valid"]:
                raise SubmitError("تراکنش خارج از بازه‌ی اعتبار است")
            txns.append(t)

        if len(txns) > 1:
            g = group_id_of(txns)
            if any(t.get("group") != g for t in txns):
                raise SubmitError("گروه تراکنش‌ها معتبر نیست")
        elif "group" in txns[0] and txns[0]["group"] != group_id_of(txns):
            raise SubmitError("گروه تراکنش معتبر نیست")

        for t in txns:
            need = MIN_FEE
            if t["type"] == "appl" and t.get("op") in ("withdraw", "delete"):
                need = 2 * MIN_FEE          # outer call plus one inner payment
            if t["fee"] < need:
                raise SubmitError(f"کارمزد کافی نیست؛ حداقل {need} میکروالگو لازم است")
            _transfer(L, c, t["sender"], L["fee_sink"], t["fee"])

        head = txns[0]
        if (len(txns) == 2 and head["type"] == "pay" and txns[1]["type"] == "appl"
                and txns[1].get("op") in ("init", "deposit")):
            self._group_op(L, c, head, txns[1])
        elif len(txns) == 1 and head["type"] == "pay":
            _transfer(L, c, head["sender"], head["receiver"], head["amount"])
        elif len(txns) == 1 and head["type"] == "appl":
            if head["op"] in ("init", "deposit"):
                raise SubmitError("این عملیات باید همراه تراکنش پرداخت در یک گروه باشد")
            self._single_op(L, c, head)
        else:
            raise SubmitError("ساختار گروه تراکنش نامعتبر است")

        for addr in c["touched"]:
            _check_min(L, addr)

    def _group_op(self, L, c, pay, call):
        sender = call["sender"]
        if pay["sender"] != sender:
            raise SubmitError("فرستنده‌ی پرداخت و فراخوانی قرارداد باید یکی باشد")
        a = _get_app(L, call["app_id"])

        if call["op"] == "init":
            if a["active"]:
                raise SubmitError("این قرارداد قبلاً فعال شده است")
            if sender != a["creator"]:
                raise SubmitError("فقط سازنده‌ی قرارداد می‌تواند آن را فعال کند")
            if pay["receiver"] != a["address"] or pay["amount"] != APP_FUND:
                raise SubmitError("پرداخت فعال‌سازی نامعتبر است")
            _transfer(L, c, sender, a["address"], APP_FUND)
            a["active"] = 1
            a["due_at"] = c["now"] + a["due_secs"]
            _event(L, c, a["id"], "activated")
            return

        # deposit
        if not a["active"]:
            raise SubmitError("قرارداد هنوز فعال نشده است")
        if a["settled_at"]:
            raise SubmitError("قرارداد تسویه شده و دیگر واریزی ندارد")
        role = _role(a, sender)
        if role is None:
            raise SubmitError("فقط خریدار یا فروشنده‌ی این قرارداد می‌تواند واریز کند")
        if a["locked"]:
            raise SubmitError("وثیقه‌ها قفل شده‌اند؛ دیگر واریزی ممکن نیست")
        amt = call["args"]["amount"]
        if pay["receiver"] != a["address"] or pay["amount"] != amt:
            raise SubmitError("پرداخت واریز نامعتبر است")
        _transfer(L, c, sender, a["address"], amt)
        a["dep_b" if role == "buyer" else "dep_s"] += amt
        _event(L, c, a["id"], "deposit", who=role[0], amount=amt,
               dep_b=a["dep_b"], dep_s=a["dep_s"])
        if a["dep_b"] >= a["agreed"] and a["dep_s"] >= a["agreed"]:
            a["locked"] = 1
            _event(L, c, a["id"], "locked", agreed=a["agreed"])

    def _single_op(self, L, c, t):
        op, sender = t["op"], t["sender"]
        if op == "create":
            return self._create(L, c, t)

        a = _get_app(L, t["app_id"])
        role = _role(a, sender)

        if op == "delete":
            if sender != a["creator"]:
                raise SubmitError("فقط سازنده‌ی قرارداد می‌تواند آن را حذف کند")
            if not a["settled_at"]:
                raise SubmitError("حذف قرارداد فقط پس از تسویه ممکن است")
            bal = L["balances"].get(a["address"], 0)
            if bal:
                _transfer(L, c, a["address"], sender, bal)
            a["exists"] = False
            _event(L, c, a["id"], "deleted")
            return

        if role is None:
            raise SubmitError("فقط طرف این قرارداد می‌تواند این عملیات را انجام دهد")
        if a["settled_at"]:
            raise SubmitError("قرارداد تسویه شده است")

        if op == "withdraw":
            amt = t["args"]["amount"]
            if not isinstance(amt, int) or amt <= 0:
                raise SubmitError("مبلغ برداشت نامعتبر است")
            key = "dep_b" if role == "buyer" else "dep_s"
            if a["approval_hash"] == EVIL_HASH:
                # The tampered program does not enforce the lock. This is the
                # attack that the signed release check is meant to catch.
                if amt > L["balances"].get(a["address"], 0) - APP_FUND:
                    raise SubmitError("موجودی قرارداد برای این برداشت کافی نیست")
                a[key] = max(0, a[key] - amt)
            else:
                free = a[key] - (a["agreed"] if a["locked"] else 0)
                if amt > free:
                    if a["locked"]:
                        raise SubmitError("وثیقه‌ی قفل‌شده قابل برداشت نیست؛ فقط مازاد آزاد برداشتنی است")
                    raise SubmitError("مبلغ بیشتر از واریزی شماست")
                a[key] -= amt
            _transfer(L, c, a["address"], sender, amt)
            _event(L, c, a["id"], "withdraw", who=role[0], amount=amt, locked=bool(a["locked"]))
            return

        if op == "mark_paid":
            if role != "buyer":
                raise SubmitError("فقط خریدار می‌تواند پرداخت را ثبت کند")
            if not a["locked"]:
                raise SubmitError("پیش از قفل شدن وثیقه‌ها نمی‌توان پرداخت را ثبت کرد")
            if a["paid_at"]:
                raise SubmitError("پرداخت قبلاً ثبت شده است")
            a["paid_at"] = c["now"]
            _event(L, c, a["id"], "paid")
            return

        if op == "mark_shipped":
            if role != "seller":
                raise SubmitError("فقط فروشنده می‌تواند ارسال کالا را ثبت کند")
            if not a["locked"]:
                raise SubmitError("پیش از قفل شدن وثیقه‌ها نمی‌توان ارسال را ثبت کرد")
            if a["shipped_at"]:
                raise SubmitError("ارسال قبلاً ثبت شده است")
            a["shipped_at"] = c["now"]
            _event(L, c, a["id"], "shipped")
            return

        if op == "enter_code":
            if role == "buyer":
                if not a["paid_at"]:
                    raise SubmitError("ابتدا خریدار باید پرداخت را ثبت کند")
                if a["ent_b"]:
                    raise SubmitError("این کد قبلاً ثبت شده است")
                kind, signer, flag = LmarketV1.KIND_PAY, a["seller"], "ent_b"
            else:
                if not a["shipped_at"]:
                    raise SubmitError("ابتدا فروشنده باید ارسال کالا را ثبت کند")
                if a["ent_s"]:
                    raise SubmitError("این کد قبلاً ثبت شده است")
                kind, signer, flag = LmarketV1.KIND_GOODS, a["buyer"], "ent_s"
            self._verify_code(a, t["args"]["code"], kind, signer)
            a[flag] = 1
            _event(L, c, a["id"], "code_entered", who=role[0])
            if a["ent_b"] and a["ent_s"]:
                self._settle(L, c, a)
            return

        raise SubmitError("عملیات ناشناخته است")

    def _create(self, L, c, t):
        args, sender = t["args"], t["sender"]
        buyer, seller = args["buyer"], args["seller"]
        if sender not in (buyer, seller):
            raise SubmitError("فقط خریدار یا فروشنده می‌تواند این قرارداد را بسازد")
        if buyer == seller:
            raise SubmitError("خریدار و فروشنده نمی‌توانند یکی باشند")
        for addr in (buyer, seller):
            try:
                decode_address(addr)
            except ValueError:
                raise SubmitError("آدرس وارد شده نامعتبر است") from None
        agreed = args["agreed"]
        if not isinstance(agreed, int) or agreed < MIN_AGREED:
            raise SubmitError(f"مبلغ وثیقه کمتر از حداقل مجاز ({MIN_AGREED} میکروالگو) است")
        due = args["due_secs"]
        if not isinstance(due, int) or not MIN_DUE <= due <= MAX_DUE:
            raise SubmitError("مهلت قرارداد باید بین ۱ تا ۳۶۵ روز باشد")
        if args.get("approval_hash") not in KNOWN_HASHES:
            raise SubmitError("برنامه‌ی قرارداد ناشناخته است؛ فقط نسخه‌های شناخته‌شده مجازند")

        app_id = L["next_app_id"]
        L["next_app_id"] += 1
        addr = app_address(app_id)
        L["app_addrs"][addr] = app_id
        L["apps"][app_id] = {
            "id": app_id, "address": addr, "exists": True,
            "creator": sender, "buyer": buyer, "seller": seller,
            "agreed": agreed, "due_secs": due, "approval_hash": args["approval_hash"],
            "version": VERSION, "created_at": c["now"], "due_at": 0,
            "active": 0, "locked": 0, "dep_b": 0, "dep_s": 0,
            "paid_at": 0, "shipped_at": 0, "ent_b": 0, "ent_s": 0, "settled_at": 0,
        }
        c["touched"].add(sender)
        _event(L, c, app_id, "created", agreed=agreed, due_secs=due)

    def _verify_code(self, a, raw, kind, signer):
        norm = str(raw).replace("-", "").replace(" ", "").upper()
        if len(norm) != 103:
            raise SubmitError("طول کد نامعتبر است؛ کد باید ۱۰۳ نویسه باشد")
        try:
            sig = base64.b32decode(norm + "=")
        except (ValueError, TypeError):
            raise SubmitError("کد نامعتبر است") from None
        msg = LmarketV1.code_message(a["version"], self.genesis_id, a["id"], kind)
        try:
            Ed25519PublicKey.from_public_bytes(decode_address(signer)).verify(sig, msg)
        except (InvalidSignature, ValueError):
            raise SubmitError("کد معتبر نیست؛ این کد از طرف مقابل و برای همین معامله صادر نشده") from None

    def _settle(self, L, c, a):
        rb, rs = a["dep_b"], a["dep_s"]
        if rb:
            _transfer(L, c, a["address"], a["buyer"], rb)
        if rs:
            _transfer(L, c, a["address"], a["seller"], rs)
        a["dep_b"] = a["dep_s"] = 0
        a["settled_at"] = c["now"]
        _event(L, c, a["id"], "settled", released_b=rb, released_s=rs,
               seconds=c["now"] - a["created_at"])

    # ---- public API
    def submit(self, signed):
        if self.faults["offline"]:
            raise SubmitError("گره در دسترس نیست")
        if not signed:
            raise SubmitError("تراکنشی ارسال نشده است")
        txns = [s["txn"] for s in signed]
        gid = group_id_of(txns) if len(txns) > 1 else _txid(signed[0])
        rec = self.txs.get(gid)
        if rec and rec["status"] in ("pending", "confirmed"):
            raise SubmitError("تراکنش تکراری است")
        work = copy.deepcopy(self.L)
        self._exec(work, signed, gid, self.round, self.now())   # dry run on a copy
        self.txs[gid] = {"status": "pending", "round": None, "error": "",
                         "last_valid": min(t["last_valid"] for t in txns)}
        self.pool.append({"gid": gid, "signed": copy.deepcopy(signed)})
        return gid

    def produce_block(self):
        if self.faults["paused"]:
            return None
        self.round += 1
        now = self.now()
        keep = []
        for entry in self.pool:
            rec = self.txs[entry["gid"]]
            if self.round > rec["last_valid"]:
                rec["status"] = "expired"
                continue
            if self.faults["drop_next"] > 0:
                self.faults["drop_next"] -= 1
                keep.append(entry)
                continue
            work = copy.deepcopy(self.L)
            try:
                self._exec(work, entry["signed"], entry["gid"], self.round, now)
                self.L = work
                rec.update(status="confirmed", round=self.round, error="")
            except SubmitError as ex:
                rec.update(status="rejected", round=self.round, error=str(ex))
        self.pool = keep
        return self.round

    def advance(self, seconds):
        seconds = int(seconds)
        if seconds < 0:
            raise ValueError("cannot move time backwards")
        self.offset += seconds
        self.round += seconds // SETTINGS["BLOCK_TIME"]

    def set_fault(self, **kw):
        for k, v in kw.items():
            if k not in self.faults:
                raise KeyError(k)
            self.faults[k] = v

    def fund(self, address, amount):
        decode_address(address)
        work = copy.deepcopy(self.L)
        c = {"rnd": self.round, "now": self.now(), "gid": "FUND", "touched": set()}
        _transfer(work, c, work["dispenser"], address, int(amount))
        _check_min(work, address)
        self.L = work


# ----------------------------------------------------------------- demo world
def _send(chain, w, intent):
    txns, _ = build_group(chain, w.address, intent)
    gid = chain.submit([w.sign_txn(t) for t in txns])
    chain.produce_block()
    st = chain.tx_status(gid)
    if st["status"] != "confirmed":
        raise RuntimeError(f"demo step failed: {st}")
    return st


def _trade(chain, seller, buyer, agreed):
    """A full settled trade. Returns the app id."""
    app = chain.next_app_id
    _send(chain, seller, dict(kind="create", buyer=buyer.address, seller=seller.address,
                              agreed=agreed, due_secs=7 * DAY, approval_hash=OFFICIAL_HASH))
    _send(chain, seller, dict(kind="init", app_id=app))
    _send(chain, seller, dict(kind="deposit", app_id=app, amount=agreed))
    _send(chain, buyer, dict(kind="deposit", app_id=app, amount=agreed))
    _send(chain, buyer, dict(kind="mark_paid", app_id=app))
    _send(chain, seller, dict(kind="mark_shipped", app_id=app))
    info = chain.app_info(app)
    _send(chain, buyer, dict(kind="enter_code", app_id=app,
                             code=code_for(seller, chain, info, LmarketV1.KIND_PAY)))
    _send(chain, seller, dict(kind="enter_code", app_id=app,
                              code=code_for(buyer, chain, info, LmarketV1.KIND_GOODS)))
    return app


def make_demo_world(clock=None):
    """Returns (chain, wallets). Alice: 14 settled trades, 800-day-old wallet.
    Dave: 20 open contracts (18 past due). Mallory: brand-new, no history."""
    chain = Chain(clock)
    W = {n: Wallet(n) for n in ("Alice", "Bob", "Mallory", "Dave")}
    A, B, M, D = W["Alice"], W["Bob"], W["Mallory"], W["Dave"]

    chain.offset = -800 * DAY
    chain.fund(A.address, 1000 * ALGO)
    chain.fund(B.address, 1000 * ALGO)
    for _ in range(14):
        app = _trade(chain, A, B, 2 * ALGO)
        _send(chain, A, dict(kind="delete", app_id=app))

    chain.offset = -120 * DAY
    chain.fund(D.address, 1000 * ALGO)
    for i in range(20):
        due = 7 if i < 18 else 365
        app = chain.next_app_id
        _send(chain, D, dict(kind="create", buyer=B.address, seller=D.address,
                             agreed=ALGO, due_secs=due * DAY, approval_hash=OFFICIAL_HASH))
        _send(chain, D, dict(kind="init", app_id=app))

    chain.offset = 0
    chain.fund(M.address, 100 * ALGO)
    return chain, W
    
if __name__ == "__main__":
    print("algosim loaded. Run tests with: py -m pytest -q test_algosim.py")
    print("Publisher public key:", _publisher()[1].hex())