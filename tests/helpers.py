"""
لایه‌ی نازک بین تست‌ها و py-algorand-sdk.

همه‌ی تماس با SDK فقط اینجاست؛ اگر نسخه‌ی SDK API ای را عوض کرده بود، فقط همین فایل اصلاح می‌شود
و تست‌ها دست‌نخورده می‌مانند. هر تراکنش و هر لاگ قرارداد با logging ثبت می‌شود
(برای دیدن: pytest -s --log-cli-level=DEBUG).
"""
import base64
import contextlib
import logging
import pathlib
import re
import sys
from dataclasses import dataclass

from algosdk import abi, account, encoding, kmd, logic, transaction
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.error import AlgodHTTPError
from algosdk.source_map import SourceMap
from algosdk.v2client import algod

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
import pytest  # noqa: E402

log = logging.getLogger("lmarket.test")

ALGO = 1_000_000
CREATE_SIG = "create(address,address,uint64,uint64)void"

# پیام خطایی که algod برای رد شدن منطق برنامه برمی‌گرداند
REJECT_PATTERN = "assert failed|err opcode|logic eval error|rejected by ApprovalProgram"


@dataclass
class Actor:
    name: str
    address: str
    sk: str

    @property
    def signer(self):
        return AccountTransactionSigner(self.sk)


# ------------------------------------------------------------------ اتصال‌ها
def algod_client() -> algod.AlgodClient:
    return algod.AlgodClient(config.ALGOD_TOKEN, config.ALGOD_URL)


def _dispenser() -> Actor:
    """حساب پردار localnet را از KMD پیدا می‌کند (بزرگ‌ترین موجودی در کیف پول پیش‌فرض)."""
    k = kmd.KMDClient(config.KMD_TOKEN, config.KMD_URL)
    wallet = next(w for w in k.list_wallets() if w["name"] == "unencrypted-default-wallet")
    handle = k.init_wallet_handle(wallet["id"], "")
    try:
        addrs = k.list_keys(handle)
        c = algod_client()
        best = max(addrs, key=lambda a: c.account_info(a)["amount"])
        return Actor("dispenser", best, k.export_key(handle, "", best))
    finally:
        k.release_wallet_handle(handle)


_dispenser_cache: Actor | None = None


def dispenser() -> Actor:
    global _dispenser_cache
    if _dispenser_cache is None:
        _dispenser_cache = _dispenser()
        log.debug("dispenser=%s", _dispenser_cache.address)
    return _dispenser_cache


# ------------------------------------------------------------------ حساب‌ها
def send_payment(src: Actor, dst: str, amount: int) -> str:
    c = algod_client()
    txn = transaction.PaymentTxn(src.address, c.suggested_params(), dst, amount)
    txid = c.send_transaction(src.signer.sign_transactions([txn], [0])[0])
    transaction.wait_for_confirmation(c, txid, 4)
    log.debug("pay %s -> %s amount=%d txid=%s", src.name, dst[:8], amount, txid)
    return txid


def new_actor(name: str, funded: int = 10 * ALGO) -> Actor:
    sk, addr = account.generate_account()
    a = Actor(name, addr, sk)
    send_payment(dispenser(), addr, funded)
    return a


def balance(addr: str) -> int:
    return algod_client().account_info(addr)["amount"]


# ------------------------------------------------------------------ برنامه‌ی کامپایل‌شده
def _build_path(suffix: str) -> pathlib.Path:
    return ROOT / config.BUILD_DIR / f"{config.CONTRACT_NAME}.{suffix}.teal"


def build_exists() -> bool:
    return _build_path("approval").exists() and _build_path("clear").exists()


def compile_teal(kind: str) -> bytes:
    """TEAL کامپایل‌شده توسط puyapy را با algod به بایت‌کد تبدیل می‌کند."""
    src = _build_path(kind).read_text(encoding="utf-8")
    return base64.b64decode(algod_client().compile(src)["result"])


# ------------------------------------------------------------------ اجرای فراخوانی‌ها
def _log_app_logs(result) -> None:
    for r in result.abi_results:
        for entry in r.tx_info.get("logs", []):
            raw = base64.b64decode(entry)
            try:
                log.debug("app-log: %s", raw.decode())
            except UnicodeDecodeError:
                log.debug("app-log(bytes): %s", raw.hex())


def deploy(creator: Actor, buyer: str, seller: str, agreed: int, due_secs: int) -> int:
    """قرارداد را می‌سازد و app_id را برمی‌گرداند. اگر منطق رد کند AlgodHTTPError می‌دهد."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=0,
        method=abi.Method.from_signature(CREATE_SIG),
        sender=creator.address,
        sp=c.suggested_params(),
        signer=creator.signer,
        method_args=[buyer, seller, agreed, due_secs],
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=compile_teal("approval"),
        clear_program=compile_teal("clear"),
        global_schema=transaction.StateSchema(config.GLOBAL_UINTS, config.GLOBAL_BYTES),
        local_schema=transaction.StateSchema(0, 0),
    )
    log.debug("deploy by=%s buyer=%s seller=%s agreed=%d due=%d",
              creator.name, buyer[:8], seller[:8], agreed, due_secs)
    result = atc.execute(c, 4)
    _log_app_logs(result)
    app_id = c.pending_transaction_info(result.tx_ids[0])["application-index"]
    log.debug("deployed app_id=%d", app_id)
    return app_id


def app_address(app_id: int) -> str:
    return logic.get_application_address(app_id)


def min_balance(addr: str) -> int:
    return algod_client().account_info(addr)["min-balance"]


def activate(app_id: int, creator: Actor, amount: int, receiver: str | None = None) -> None:
    """
    مرحله‌ی ۲: پرداخت به حساب قرارداد + فراخوانی activate در یک گروه.
    receiver پیش‌فرض آدرس قرارداد است؛ برای آزمودن مقصد اشتباه می‌توان عوض کرد.
    """
    c = algod_client()
    sp = c.suggested_params()
    pay = transaction.PaymentTxn(creator.address, sp, receiver or app_address(app_id), amount)
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("activate(pay)void"),
        sender=creator.address,
        sp=sp,
        signer=creator.signer,
        method_args=[TransactionWithSigner(pay, creator.signer)],
    )
    atc.execute(c, 4)


def deposit(app_id: int, who: Actor, amount: int, receiver: str | None = None,
            pay_from: Actor | None = None) -> None:
    """
    مرحله‌ی ۳الف: پرداخت + فراخوانی deposit در یک گروه.
    pay_from: پرداخت‌کننده‌ی دیگر (برای آزمودن این‌که فرستنده‌ی پرداخت باید خود فراخواننده باشد).
    """
    c = algod_client()
    sp = c.suggested_params()
    payer = pay_from or who
    pay = transaction.PaymentTxn(payer.address, sp, receiver or app_address(app_id), amount)
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("deposit(pay)void"),
        sender=who.address,
        sp=sp,
        signer=who.signer,
        method_args=[TransactionWithSigner(pay, payer.signer)],
    )
    atc.execute(c, 4)


def mark_paid(app_id: int, who: Actor) -> None:
    """مرحله‌ی ۴الف: ثبت پرداخت توسط خریدار (بدون آرگومان)."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("mark_paid()void"),
        sender=who.address,
        sp=c.suggested_params(),
        signer=who.signer,
    )
    atc.execute(c, 4)


def mark_shipped(app_id: int, who: Actor) -> None:
    """مرحله‌ی ۴ب: ثبت ارسال توسط فروشنده (بدون آرگومان)."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("mark_shipped()void"),
        sender=who.address,
        sp=c.suggested_params(),
        signer=who.signer,
    )
    atc.execute(c, 4)


def register_key(app_id: int, who: Actor, key: bytes) -> None:
    """مرحله‌ی ۵الف: ثبت کلید عمومی Ed25519 (آرگومان: byte[])."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("register_key(byte[])void"),
        sender=who.address,
        sp=c.suggested_params(),
        signer=who.signer,
        method_args=[key],
    )
    atc.execute(c, 4)


def rotate_key(app_id: int, who: Actor, key: bytes) -> None:
    """مرحله‌ی ۵الف۲: تعویض کلید عمومی Ed25519 (آرگومان: byte[])."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("rotate_key(byte[])void"),
        sender=who.address,
        sp=c.suggested_params(),
        signer=who.signer,
        method_args=[key],
    )
    atc.execute(c, 4)


def genesis_hash() -> bytes:
    """هش ژنسیس شبکه‌ی جاری (۳۲ بایت)؛ بخشی از پیام امضا."""
    return base64.b64decode(algod_client().suggested_params().gh)


def message(app_id: int, who: Actor, role: int) -> bytes:
    """مرحله‌ی ۵پ: پیام امضای ساخته‌شده توسط قرارداد (فقط‌خواندنی)."""
    c = algod_client()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("message(uint8)byte[]"),
        sender=who.address,
        sp=c.suggested_params(),
        signer=who.signer,
        method_args=[role],
    )
    res = atc.execute(c, 4)
    return bytes(res.abi_results[0].return_value)


WITHDRAW_FEE = 2_000   # کارمزد تراکنش بیرونی + تراکنش داخلی، که فراخواننده می‌پردازد


def withdraw(app_id: int, who: Actor, amount: int) -> None:
    """مرحله‌ی ۳الف: برداشت از واریزی خود؛ کارمزد ثابت WITHDRAW_FEE است."""
    c = algod_client()
    sp = c.suggested_params()
    sp.flat_fee = True
    sp.fee = WITHDRAW_FEE
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=abi.Method.from_signature("withdraw(uint64)void"),
        sender=who.address,
        sp=sp,
        signer=who.signer,
        method_args=[amount],
    )
    atc.execute(c, 4)


def raw_app_txn(sender: Actor, kind: str, app_id: int) -> None:
    """update/delete خام (بدون ABI)؛ برای آزمودن این‌که برنامه تغییرناپذیر است."""
    c = algod_client()
    sp = c.suggested_params()
    if kind == "update":
        prog = compile_teal("clear")  # هر برنامه‌ی معتبر؛ هدف فقط رد شدن است
        txn = transaction.ApplicationUpdateTxn(sender.address, sp, app_id, prog, prog)
    elif kind == "delete":
        txn = transaction.ApplicationDeleteTxn(sender.address, sp, app_id)
    elif kind == "optin":
        txn = transaction.ApplicationOptInTxn(sender.address, sp, app_id)
    else:
        raise ValueError(kind)
    txid = c.send_transaction(sender.signer.sign_transactions([txn], [0])[0])
    transaction.wait_for_confirmation(c, txid, 4)


# ------------------------------------------------------------------ دلیل رد شدن
def _message_from_teal(lines: list, idx: int):
    """
    puyapy پیام هر assert را کنار همان خط TEAL می‌نویسد، مثلاً `assert // agreed below minimum`.
    خط نگاشت‌شده را (با تحمل خطای ±۱ در شماره‌گذاری) پیدا می‌کنیم و پیام را برمی‌گردانیم.
    """
    for j in (idx, idx - 1, idx + 1):
        if 0 <= j < len(lines):
            code, _, comment = lines[j].partition("//")
            parts = code.split()
            if parts and parts[0] in ("assert", "err") and comment.strip():
                return comment.strip()
    return None


_sourcemap_cache: dict = {}


def failure_reason(exc: Exception):
    """پیام assert قرارداد را از روی pc موجود در خطای algod و نقشه‌ی منبع برمی‌گرداند (یا None)."""
    m = re.search(r"pc=(\d+)", str(exc))
    if not m:
        return None
    if "approval" not in _sourcemap_cache:
        src = _build_path("approval").read_text(encoding="utf-8")
        res = algod_client().compile(src, source_map=True)
        _sourcemap_cache["approval"] = (SourceMap(res["sourcemap"]), src.splitlines())
    sm, lines = _sourcemap_cache["approval"]
    line = sm.get_line_for_pc(int(m.group(1)))
    if line is None:
        return None
    return _message_from_teal(lines, line)


@contextlib.contextmanager
def rejected(expected_reason: str):
    """بلاک باید با همین پیام assert رد شود؛ پذیرفته شدن یا رد شدن به دلیل دیگر، تست را می‌شکند."""
    try:
        yield
    except AlgodHTTPError as e:
        reason = failure_reason(e)
        assert reason is not None and expected_reason in reason, (
            f"rejected for the wrong reason: got {reason!r}, expected {expected_reason!r}; raw error: {e}")
        log.debug("rejected as expected: %s", reason)
    else:
        pytest.fail(f"call was accepted but should have been rejected ({expected_reason!r})")


# ------------------------------------------------------------------ خواندن وضعیت
def read_state(app_id: int) -> dict:
    """حافظه‌ی سراسری قرارداد؛ مقدارهای ۳۲بایتی به آدرس تبدیل می‌شوند."""
    out = {}
    params = algod_client().application_info(app_id)["params"]
    for kv in params.get("global-state", []):
        key = base64.b64decode(kv["key"]).decode()
        v = kv["value"]
        if v["type"] == 2:
            out[key] = v.get("uint", 0)
        else:
            raw = base64.b64decode(v["bytes"])
            out[key] = encoding.encode_address(raw) if len(raw) == 32 else raw
    log.debug("state app=%d %s", app_id, out)
    return out


__all__ = ["ALGO", "Actor", "AlgodHTTPError", "REJECT_PATTERN", "rejected"]
