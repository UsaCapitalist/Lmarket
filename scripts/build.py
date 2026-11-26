"""
کامپایل قرارداد با puyapy و چاپ هش SHA-256 برنامه‌ی TEAL.
اجرا:  python scripts/build.py

هش TEAL کامپایل‌شده همان چیزی است که شبکه اجرا می‌کند (نه سورس پایتون).
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402


def main() -> int:
    exe = shutil.which("puyapy")
    if not exe:
        print("[build] puyapy پیدا نشد. محیط مجازی فعال است؟ (گام ۲ و ۴ README)")
        return 1
    cmd = [exe, "--out-dir", config.BUILD_DIR, config.CONTRACT_FILE]
    print("[build] اجرا:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print("[build] کامپایل ناموفق بود. اگر خطا درباره‌ی گزینه‌ی --out-dir است، "
              "`puyapy --help` را اجرا کنید و خروجی را بفرستید.")
        return rc
    teal = ROOT / config.BUILD_DIR / f"{config.CONTRACT_NAME}.approval.teal"
    if not teal.exists():
        print("[build] فایل TEAL پیدا نشد:", teal)
        print("[build] محتوای پوشه‌ی build:", sorted(p.name for p in (ROOT / config.BUILD_DIR).glob("*")))
        return 1
    print("[build] approval sha256:", hashlib.sha256(teal.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
