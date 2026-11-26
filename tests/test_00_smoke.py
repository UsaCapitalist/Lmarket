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
    src = (helpers.ROOT / config.CONTRACT_FILE).read_text()
    for name in ("MIN_AGREED", "MIN_DUE_SECS", "MAX_DUE_SECS"):
        m = re.search(rf"^{name}\s*=\s*([\d_]+)", src, re.M)
        assert m, f"{name} not found in contract source"
        assert int(m.group(1).replace("_", "")) == getattr(config, name), name
