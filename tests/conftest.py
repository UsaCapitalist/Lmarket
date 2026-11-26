"""فیکسچرهای مشترک تست‌ها. تنظیم لاگ از config.LOG_LEVEL خوانده می‌شود."""
import logging
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import config  # noqa: E402
import helpers  # noqa: E402

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format="%(levelname)s %(name)s: %(message)s")


@pytest.fixture
def alice():
    """فروشنده (حساب تازه با ۱۰ ALGO در هر تست؛ تست‌ها از هم مستقل‌اند)"""
    return helpers.new_actor("alice")


@pytest.fixture
def bob():
    """خریدار"""
    return helpers.new_actor("bob")


@pytest.fixture
def mallory():
    """مهاجم (طرف قرارداد نیست)"""
    return helpers.new_actor("mallory")
