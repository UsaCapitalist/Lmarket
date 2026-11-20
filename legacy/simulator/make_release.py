"""
make_release.py - امضای نسخه‌ی قرارداد با کلید ناشر و نوشتن release.json کنار index.html.

کلید خصوصی ناشر در ~/.lmarket/publisher_key.json است (بیرون از پوشه‌ی وب و مخزن).
این اسکریپت را فقط روی ماشین ناشر اجرا کنید. سرور هیچ کلیدی ندارد.
اجرا:  python3 make_release.py
"""
import json
import os

import algosim as sim

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    manifest = sim.release_manifest()
    out = os.path.join(HERE, "release.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("release.json written:", out)
    print("publisher (CONFIG.publisher در index.html):", manifest["publisher"])


if __name__ == "__main__":
    main()
