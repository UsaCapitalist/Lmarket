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
        print("[build] puyapy not found. Is the virtual environment active? (prompt must start with (.venv); README steps 2 and 4)")
        return 1
    # مسیر مطلق: puyapy مسیر نسبی را نسبت به پوشه‌ی فایل قرارداد حل می‌کند (contracts/build)
    cmd = [exe, "--out-dir", str(ROOT / config.BUILD_DIR), config.CONTRACT_FILE]
    print("[build] running:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print("[build] compile failed. If the error mentions --out-dir, run `puyapy --help` and report the output.")
        return rc
    teal = ROOT / config.BUILD_DIR / f"{config.CONTRACT_NAME}.approval.teal"
    if not teal.exists():
        print("[build] TEAL file not found:", teal)
        print("[build] build dir contents:", sorted(p.name for p in (ROOT / config.BUILD_DIR).glob("*")))
        return 1
    print("[build] approval TEAL sha256:", hashlib.sha256(teal.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
