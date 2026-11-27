"""
تنظیمات پروژه (بدون متغیر محیطی؛ همه‌چیز همین‌جا).

مقادیر پیش‌فرض مربوط به localnet الگوکیت است. برای testnet این فایل را کپی و ویرایش کنید،
ولی هرگز mnemonic یا کلید خصوصی را اینجا ننویسید.
"""

# سطح لاگ تست‌ها: "DEBUG" | "INFO" | "WARNING" | "ERROR"
LOG_LEVEL = "DEBUG"

# localnet پیش‌فرض algokit
ALGOD_URL = "http://localhost:4001"
ALGOD_TOKEN = "a" * 64
KMD_URL = "http://localhost:4002"
KMD_TOKEN = "a" * 64

# خروجی کامپایل
BUILD_DIR = "build"
CONTRACT_FILE = "contracts/lmarket.py"
CONTRACT_NAME = "Lmarket"            # نام کلاس قرارداد؛ نام فایل‌های TEAL از آن می‌آید

# اندازه‌ی حافظه‌ی سراسری قرارداد. در مرحله‌ی آخر با عدد دقیق جایگزین می‌شود
# (هر اسلات اضافه، موجودی حداقلِ سازنده را بی‌دلیل بالا می‌برد).
GLOBAL_UINTS = 24
GLOBAL_BYTES = 8

# ----- مقادیر قرارداد: باید دقیقاً با ثابت‌های بالای contracts/lmarket.py یکی باشند.
# تست test_00_smoke.py::test_constants_match این یکی‌بودن را بررسی می‌کند.
MIN_AGREED = 100_000                 # microAlgo (۰٫۱ ALGO)
MIN_DUE_SECS = 3_600                 # یک ساعت
MAX_DUE_SECS = 31_536_000            # ۳۶۵ روز
APP_FUND = 1_200_000                 # microAlgo؛ باید با حداقل موجودی حساب قرارداد (min-balance) بالاتر یا برابر باشد؛ تست stage 2 بررسی می‌کند
