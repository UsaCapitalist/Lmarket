"""
مرجع خالص (بدون زنجیره) برای پیامی که هر طرف برای کد تأیید امضا می‌کند (مرحله‌ی 5b).
قرارداد همین قالب را از حافظه‌ی خودش می‌سازد و تست‌ها خروجی آن را با این تابع مقایسه می‌کنند.
رابط جاوااسکریپت (index.html) بعداً باید دقیقاً همین بردار تست ثابت را بازتولید کند.

قالب (طول ثابت ۱۵۵ بایت، بدون جداکننده؛ عددها ۸بایتی big-endian):
  "LMARKET-V1"(10) | نقش(1) | genesis_hash(32) | app_id(8) | buyer(32) | seller(32)
  | agreed(8) | due_secs(8) | created_at(8) | activated_at(8) | locked_at(8)
نقش: 1 = فروشنده دریافت وجه را تأیید می‌کند، 2 = خریدار دریافت کالا را تأیید می‌کند.
فقط داده‌هایی که تا لحظه‌ی قفل ثابت شده‌اند در پیام هستند.
"""

DOMAIN = b"LMARKET-V1"
ROLE_SELLER_CONFIRMS_FUNDS = 1
ROLE_BUYER_CONFIRMS_GOODS = 2
MESSAGE_LEN = 155


def u64(n: int) -> bytes:
    return n.to_bytes(8, "big")


def build_message(role: int, genesis_hash: bytes, app_id: int, buyer: bytes, seller: bytes,
                  agreed: int, due_secs: int, created_at: int, activated_at: int, locked_at: int) -> bytes:
    assert role in (1, 2) and len(genesis_hash) == 32 and len(buyer) == 32 and len(seller) == 32
    msg = (DOMAIN + bytes([role]) + genesis_hash + u64(app_id) + buyer + seller
           + u64(agreed) + u64(due_secs) + u64(created_at) + u64(activated_at) + u64(locked_at))
    assert len(msg) == MESSAGE_LEN
    return msg
