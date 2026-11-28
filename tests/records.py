"""
رمزگشای خالص رکوردهای log قرارداد (بدون زنجیره). رابط جاوااسکریپت و ابزار اعتبار باید همین قالب را بخوانند.

رکورد برداشت (5f): EVENT:withdrawn_v1(18 بایت ASCII) | برداشت‌کننده(1: B خریدار، S فروشنده) | مبلغ(8) | زمان(8)
                    | قفل‌بودن(1) | واریزی طرف مقابل(8) | واریزی باقی‌مانده‌ی برداشت‌کننده(8)  → ۵۲ بایت
"""

WITHDRAW_PREFIX = b"EVENT:withdrawn_v1"
WITHDRAW_LEN = 52


def decode_withdraw(raw: bytes) -> dict:
    assert raw.startswith(WITHDRAW_PREFIX) and len(raw) == WITHDRAW_LEN, raw.hex()
    b = raw[len(WITHDRAW_PREFIX):]
    n = lambda x: int.from_bytes(x, "big")
    return {
        "who": b[0:1].decode(),
        "amount": n(b[1:9]),
        "time": n(b[9:17]),
        "locked": b[17],
        "other_dep": n(b[18:26]),
        "own_after": n(b[26:34]),
    }


def withdraw_records(logs: list) -> list:
    return [decode_withdraw(x) for x in logs if x.startswith(WITHDRAW_PREFIX)]
