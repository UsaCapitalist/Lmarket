"""
مرحله‌ی ۰: سلامت ابزارها (هنوز چیزی از منطق قرارداد آزموده نمی‌شود).
اگر این تست‌ها نگذرند، مشکل از محیط است نه قرارداد.
"""
import re

import config
import helpers
from helpers import ALGO


def test_algod_reachable():
    st = helpers.algod_client().status()
    assert st["last-round"] >= 0


def test_dispenser_is_funded():
    assert helpers.balance(helpers.dispenser().address) > 1000 * ALGO


def test_new_actor_is_funded():
    a = helpers.new_actor("probe", 3 * ALGO)
    assert helpers.balance(a.address) == 3 * ALGO


def test_build_output_exists():
    assert helpers.build_exists(), "build output missing: run `python scripts/build.py` first (README step 6)"


def test_programs_compile_on_algod():
    assert len(helpers.compile_teal("approval")) > 0
    assert len(helpers.compile_teal("clear")) > 0


def test_constants_match():
    """ثابت‌های contracts/lmarket.py باید با config.py یکی باشند."""
    src = (helpers.ROOT / config.CONTRACT_FILE).read_text(encoding="utf-8")
    for name in ("MIN_AGREED", "MIN_DUE_SECS", "MAX_DUE_SECS", "APP_FUND"):
        m = re.search(rf"^{name}\s*=\s*([\d_]+)", src, re.M)
        assert m, f"{name} not found in contract source"
        assert int(m.group(1).replace("_", "")) == getattr(config, name), name


def test_teal_keeps_assert_messages():
    """
    تست‌های رد‌شدن به پیام assert تکیه می‌کنند. اگر کامپایلر پیام‌ها را در TEAL نگذاشته باشد،
    این تست همان‌جا و با پیام روشن می‌شکند.
    """
    teal = helpers._build_path("approval").read_text(encoding="utf-8")
    for msg in ("buyer and seller must differ", "only buyer or seller may create", "agreed below minimum",
                "already activated", "only creator may activate", "activation payment must equal APP_FUND",
                "contract not activated", "only buyer or seller may deposit", "deposit must be positive",
                "withdraw exceeds deposit", "only buyer or seller may withdraw", "withdraw exceeds free balance"):
        assert msg in teal, f"assert message {msg!r} missing from approval TEAL"


def test_message_extraction_logic():
    """منطق خالص استخراج پیام از خط TEAL (بدون زنجیره)."""
    lines = ["#pragma version 10", "assert // agreed below minimum", "err // boom", "return"]
    assert helpers._message_from_teal(lines, 1) == "agreed below minimum"
    assert helpers._message_from_teal(lines, 2) == "boom"
    assert helpers._message_from_teal(lines, 3) is None or helpers._message_from_teal(lines, 3) == "boom"
    assert helpers._message_from_teal(lines, 0) == "agreed below minimum"   # تحمل خطای ±۱
