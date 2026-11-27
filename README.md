# Lmarket · سفته‌ی دیجیتال / Digital Promissory Note

[فارسی](#فارسی) · [English](#english)

---

<a id="فارسی"></a>

## فارسی

**ال مارکت** یک پروتکل معامله‌ی شخص به شخص روی Algorand است. دو طرفی که به هم اعتماد شخصی ندارند، هر کدام وثیقه‌ای به **مبلغ برابر** قفل می‌کنند. پرداخت و تحویل کالا بیرون از زنجیره انجام می‌شود و وثیقه‌ها فقط پس از ثبت **هر دو کد تأیید** آزاد می‌شوند.

> **وضعیت این شاخه (`decentralized`):** شبیه‌ساز پایتون و کلید امضای ناشر از مخزن حذف شده‌اند. قرارداد هوشمند به‌صورت PuyaPy نوشته و روی Algorand (ابتدا localnet، سپس testnet) مستقر می‌شود. این شاخه هنوز **قرارداد نهایی ندارد**؛ قرارداد مرحله‌به‌مرحله ساخته می‌شود و فقط **مرحله‌ی ۱ (ساخت قرارداد)** و **مرحله‌ی ۲ (فعال‌سازی با `APP_FUND`)** انجام شده است. و **مرحله‌ی ۳الف (واریز و برداشت پیش از قفل)** هم انجام شده است. **مرحله‌ی ۳ب (قفل دقیق مبلغ توافقی)** هم انجام شده است: با رسیدن واریزی هر دو طرف به مبلغ توافقی، دقیقاً همان مبلغ قفل می‌شود و فقط مازاد قابل برداشت است. **مرحله‌ی ۴الف (`mark_paid`)** هم انجام شده است؛ این ثبت فقط اعلام است و وجهی آزاد نمی‌کند. **مرحله‌ی ۴ب (`mark_shipped`)** هم انجام شده است (مستقل از `mark_paid` و فقط اعلام). **مرحله‌ی ۴پ (ثبت زمان رویدادها)** هم انجام شده است. **مرحله‌ی ۵الف (ثبت کلید عمومی Ed25519)** و **مرحله‌ی ۵الف۲ (تعویض کلید)** هم انجام شده است. هنوز کد تأیید و تسویه وجود ندارد. جزئیات در بخش «وضعیت پروژه» پایین‌تر است.

### ایده‌ی اصلی

- قرارداد هوشمند نیرویی فیزیکی ندارد. امنیت از **انگیزه‌ی اقتصادی** می‌آید: اگر طرفی کار خود را نکند، وثیقه‌ی خودش قفل می‌ماند.
- قرارداد ارزش کالا، قیمت یا عادلانه بودن معامله را نمی‌سنجد. مبلغ وثیقه را دو طرف تعیین می‌کنند.
- هیچ‌کس با ادعای تنهای خود وثیقه‌ی طرف مقابل را برنمی‌دارد. قرارداد مقصر را تشخیص نمی‌دهد.
- **مدیر، به‌روزرسانی و کلید ناشر وجود ندارد.** برنامه‌ی قرارداد پس از انتشار تغییرناپذیر است. هر کسی می‌تواند با خواندن برنامه‌ی تأییدشده روی زنجیره، درستیِ آن را بررسی کند.

### جریان معامله

| مرحله | خریدار (Bob) | فروشنده (Alice) |
|---|---|---|
| ۱. ساخت و فعال‌سازی | قرارداد را می‌سازد یا فعال می‌کند | قرارداد را می‌سازد یا فعال می‌کند |
| ۲. واریز وثیقه | مبلغ توافقی را واریز می‌کند | مبلغ توافقی را واریز می‌کند |
| ۳. قفل | با رسیدن هر دو واریزی، هر دو وثیقه قفل می‌شوند | |
| ۴. پرداخت و ارسال (بیرون از زنجیره) | وجه را پرداخت می‌کند و ثبت می‌زند | کالا را می‌فرستد و ثبت می‌زند |
| ۵. تأیید دریافت وجه | کد فروشنده را وارد می‌کند | کد تأیید دریافت وجه را می‌سازد |
| ۶. تأیید دریافت کالا | کد تأیید دریافت کالا را می‌سازد | کد خریدار را وارد می‌کند |
| ۷. تسویه | با ثبت هر دو کد، وثیقه‌ها به صاحبانشان برمی‌گردد | |

- اگر یک طرف تأیید نکند، وثیقه‌ی هر دو طرف قفل می‌ماند. **مهلت خودکار وجود ندارد و این عمدی است.**
- مهلت اعلام‌شده فقط نشانه‌ی اعتبار است؛ هیچ وجهی را آزاد نمی‌کند.

### ساختار مخزن

```
lmarket/
├── README.md              # همین فایل
├── LICENSE                # Apache-2.0
├── .gitignore
├── index.html             # رابط نمایشی؛ هنوز به زنجیره وصل نیست
├── contracts/lmarket.py   # قرارداد PuyaPy (مرحله‌ی ۱)
├── config.py              # همه‌ی تنظیمات (بدون متغیر محیطی)
├── scripts/               # deploy و ابزارهای کمکی
├── tests/                 # تست‌های قرارداد روی localnet
├── build/                 # خروجی puyapy؛ در git نیست
└── legacy/simulator/      # شبیه‌ساز قدیمی پایتون (فقط آرشیو)
```

---

## وضعیت پروژه (برای ادامه‌ی کار، حتی با مدل یا توسعه‌دهنده‌ی دیگر)

**آخرین وضعیت تأییدشده:** روی ویندوز با localnet الگوکیت، `tests/test_00_smoke.py` (۸ تست)، `tests/test_01_create.py` (۱۶ تست) و `tests/test_02_activate.py` (۸ تست) `tests/test_03a_deposit.py` (۱۴ تست) و `tests/test_03b_lock.py` (۱۲ تست) `tests/test_04a_mark_paid.py` (۱۰ تست) و `tests/test_04b_mark_shipped.py` (۱۱ تست) و `tests/test_04c_timestamps.py` (۷ تست) و `tests/test_05a_register_key.py` (۱۰ تست) و `tests/test_05a2_rotate_key.py` (۱۱ تست) کاملاً سبز هستند (جمعاً ۱۰۷ تست؛ اجرا با `pytest -q`). هش TEAL تأییدی در آن اجرا: `4e21c1a458871b178e454064ba2f07c3980c035dc07127b53888a8564e324ebd`.

**نسخه‌هایی که با آن‌ها کار کرده است:** AlgoKit 2.10.2، puyapy 5.10.1، algorand-python 4.0.0، py-algorand-sdk 2.12.0، pytest 9.2.0، Python **3.12** داخل venv (پایتون سراسری ۳٫۱۵ است و نباید برای پروژه استفاده شود)، algod 5.1.1 روی localnet.

### مرحله‌ها

| مرحله | محتوا | وضعیت |
|---|---|---|
| ۰ | سلامت ابزارها (algod، حساب‌ها، کامپایل TEAL) | انجام و سبز |
| ۱ | `create` و اعتبارسنجی ورودی‌ها، تغییرناپذیری برنامه | انجام و سبز |
| ۲ | فعال‌سازی با پرداخت موجودی پایه (`APP_FUND`) | انجام و سبز |
| ۳الف | `deposit` و `withdraw` پیش از قفل، دیدن واریزی طرف مقابل | انجام و سبز |
| ۳ب | قفل دقیقِ مبلغ توافقی، مازاد آزاد و قابل برداشت | انجام و سبز |
| ۴الف | ثبت پرداخت (`mark_paid`) توسط خریدار | انجام و سبز |
| ۴ب | ثبت ارسال (`mark_shipped`) توسط فروشنده | انجام و سبز |
| ۴پ | ثبت زمان فعال‌سازی، قفل، پرداخت و ارسال (`activated_at`، `locked_at`، `paid_at`، `shipped_at`)؛ فقط ثبت‌اند | انجام و سبز |
| ۵الف | ثبت کلید عمومی Ed25519 هر طرف، یک‌بار و با زمان (`register_key`)؛ فقط ثبت | انجام و سبز |
| ۵الف۲ | تعویض کلید (`rotate_key`)، با زمان و شمارنده‌ی تعویض؛ قفل‌شدن کلید پس از ثبت کد در ۵ث می‌آید | انجام و سبز |
| ۵ | کد تأیید با امضای Ed25519 (`ed25519verify_bare`) روی پیام وابسته به شناسه‌ی قرارداد | |
| ۶ | تسویه و حذف قرارداد | |
| ۷ | تست‌های خصمانه: کد جعلی، کد قرارداد دیگر، پیش‌پرداخت به آدرس قرارداد، رقابت دو تراکنش در یک بلوک | |

هر مرحله فقط چند خط به قرارداد اضافه می‌کند و تست خودش را دارد. مرحله‌ی بعد فقط وقتی شروع می‌شود که تست‌های قبلی سبز باشند.

### قواعد طراحی (از توافق پروژه)

- بدون مدیر، بدون به‌روزرسانی، بدون کلید ناشر. تأیید صحت برنامه با هش TEAL کامپایل‌شده است، نه سورس پایتون.
- پیش از قفل، هر طرف هر لحظه واریزی خود را برمی‌دارد. با رسیدن واریزی هر دو طرف به مبلغ توافقی، **دقیقاً همان مبلغ** از هر طرف قفل می‌شود؛ مازاد آزاد و قابل برداشت می‌ماند.
- هیچ وثیقه‌ای پیش از ثبت **هر دو** کد تأیید آزاد نمی‌شود. مهلت (`due_secs`) فقط اطلاع‌رسانی است و هرگز وجهی را آزاد نمی‌کند.
- کد تأیید باید امضای Ed25519 طرف مقابل باشد، روی پیامی که به شناسه‌ی قرارداد گره خورده است تا در قرارداد دیگر قابل بازاستفاده نباشد.
- قرارداد بی‌طرف می‌ماند و حق دخالت ندارد. اعتبار (قراردادهای باز، مدت، سن کیف پول) به بازار سپرده می‌شود و رابط فقط هشدار می‌دهد.

### قواعد کار روی کد

- **خروجی ترمینال (print، پیام assert تست‌ها، لاگ) باید انگلیسی باشد.** کامنت‌ها، docstringها و مستندات فارسی می‌مانند.
- تنظیمات فقط در `config.py` است، نه متغیر محیطی. ثابت‌های بالای `contracts/lmarket.py` باید با `config.py` یکی باشند (تست `test_constants_match` بررسی می‌کند).
- تماس با py-algorand-sdk فقط در `tests/helpers.py` است تا تغییر نسخه‌ی SDK فقط یک فایل را درگیر کند.
- هر تست رد‌شدن دو چیز را ثابت می‌کند: رد شد، و به همان پیام assert مورد انتظار رد شد (`helpers.rejected`). هر رد‌شدن یک «شاهد موفق» با ورودی درست هم دارد.
- پیام‌های assert قرارداد انگلیسی‌اند و باید در TEAL به‌صورت کامنت بمانند (تست `test_teal_keeps_assert_messages`).
- بعد از هر تغییر قرارداد: `python scripts/build.py` و سپس `pytest`. هش جدید را ثبت کنید.

### مشکلات شناخته‌شده و کارهای باز

- پس از ۴پ، حافظه‌ی سراسری ۱۳ uint و ۳ بایت دارد (قبل از آن ۹ uint). پس از ۵الف۲: ۱۷ uint و ۵ بایت (`GLOBAL_UINTS` موقتاً ۲۴). `GLOBAL_UINTS` و `GLOBAL_BYTES` در `config.py` فعلاً بزرگ‌تر از نیاز هستند. در پایان باید با عدد دقیق جایگزین شوند، چون هر اسلات اضافه موجودی حداقلِ سازنده را بالا می‌برد.
- هنوز **تست پیش‌پرداخت به آدرس قرارداد** (قبل از ساخته شدن) و تست رقابت در یک بلوک وجود ندارد؛ در مرحله‌ی ۷ می‌آیند.
- `index.html` هنوز به زنجیره وصل نیست و به `release.json` و `algosim` قدیمی وابسته است. باید بازنویسی شود و هش TEAL را از زنجیره بخواند.
- این مخزن حسابرسی امنیتی نشده است. استفاده روی mainnet بدون حسابرسی مستقل ممنوع است.
- کلید خصوصی ناشر قدیمی در تاریخچه‌ی git هنوز موجود است؛ آن را افشاشده فرض کنید (بخش «امنیت و تاریخچه‌ی مخزن»).
- commit `822ed8e` هنوز ایمیل `claude@anthropic.com` دارد (فقط یک نکته‌ی ظاهری در تاریخچه).

### اجرای سریع برای بررسی وضعیت فعلی (ویندوز، با `(.venv)` فعال و localnet روشن)

```powershell
git pull
python scripts/build.py
pytest -q tests/test_00_smoke.py
pytest -q tests/test_01_create.py
```

---

## راهنمای گام‌به‌گام: از ۰ تا ۱۰۰ (کامپایل، deploy و دیباگ)

> **یادداشت صداقت:** این دستورها بر پایه‌ی مستندات رسمی AlgoKit و PuyaPy نوشته شده‌اند، اما هنوز روی ماشین توسعه‌دهنده تأیید نشده‌اند. اگر یک گام خطا داد، **خروجی کامل ترمینال** را همراه با شماره‌ی گام ذخیره کنید. همین گزارش بهترین ورودی برای اصلاح راهنماست.

### بخش الف: آماده‌سازی (۰ تا ۳۰)

**گام ۰ · پیش‌نیازها را بررسی کنید**

- Docker Desktop نصب و **در حال اجرا** باشد (localnet به آن نیاز دارد).
- Python ۳.۱۲ نصب باشد: `python3 --version` (ویندوز: `py -3.12 --version`). **Python ۳.۱۳ یا ۳.۱۵ را برای این پروژه استفاده نکنید** مگر اینکه PuyaPy آن را رسماً پشتیبانی کند.
- در ویندوز: `algokit doctor` ممکن است Node.js و Poetry را گزارش کند. برای این پروژه لازم نیستند و می‌توان آن‌ها را نادیده گرفت.
- Git نصب باشد: `git --version`

**گام ۱ · مخزن را دریافت کنید**

```bash
git clone https://github.com/UsaCapitalist/Lmarket.git
cd Lmarket
git checkout decentralized
```

**گام ۲ · محیط پایتون مجازی بسازید**

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
# ویندوز (PowerShell): حتماً نسخه‌ی ۳.۱۲ را انتخاب کنید؛ python پیش‌فرض ممکن است ۳.۱۵ باشد
py -3.12 -m venv .venv
# اگر activate خطای «running scripts is disabled» داد (فقط برای همین پنجره):
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
python -m pip install --upgrade pip
```

**گام ۳ · AlgoKit CLI را نصب کنید**

```bash
python -m pip install --user pipx
python -m pipx ensurepath
# ترمینال را ببندید و دوباره باز کنید، سپس:
pipx install algokit
algokit --version
algokit doctor
```

`algokit doctor` باید Docker، Python و Git را تأیید کند. اگر یکی ناموفق بود، همان را اصلاح کنید.

**گام ۴ · پکیج‌های پروژه را نصب کنید**

```bash
pip install -r requirements.txt
puyapy --version
```

**گام ۵ · localnet را راه‌اندازی کنید** (اولین بار چند دقیقه طول می‌کشد)

```bash
algokit localnet start
algokit localnet status
```

`status` باید algod، indexer و KMD را در حال اجرا نشان دهد. آدرس پیش‌فرض algod: `http://localhost:4001`.

### بخش ب: کامپایل (۳۰ تا ۵۰)

**گام ۶ · کامپایل قرارداد**

```bash
python scripts/build.py
# معادل دستی: puyapy --out-dir build contracts/lmarket.py
```

خروجی باید شامل این‌ها باشد:

- `*.approval.teal` و `*.clear.teal`: برنامه‌ی TEAL که روی زنجیره اجرا می‌شود.
- `*.arc56.json`: توصیف ABI قرارداد.
- `*.puya.map`: نقشه‌ی منبع (برای دیباگ).

**مهم:** بعد از `activate` باید ابتدای خط فرمان `(.venv)` دیده شود. بدون آن `pytest` و `puyapy` پیدا نمی‌شوند.

**گام ۷ · هش برنامه را ثبت کنید**

هش برنامه‌ی **کامپایل‌شده** (نه سورس پایتون) تعیین می‌کند چه کدی اجرا می‌شود. آن را ذخیره کنید؛ در مرحله‌ی تأیید رابط به آن نیاز است.

```bash
python -c "import hashlib,base64,sys; b=open('build/Lmarket.approval.teal','rb').read(); print(hashlib.sha256(b).hexdigest())"
```

**گام ۸ · خطاهای کامپایل را بخوانید**

- خطای `puyapy` معمولاً به خط و ستون اشاره دارد. آن خط را در `contracts/lmarket.py` ببینید.
- اگر خطا درباره‌ی نوع داده بود (مثلاً `UInt64` و `int`)، عبارت را با `UInt64(...)` یا `arc4.UInt64` تبدیل کنید.
- کامپایل موفق به معنای درستی منطق نیست؛ آن را در بخش تست بررسی کنید.

### بخش ج: deploy روی localnet (۵۰ تا ۷۰)

**گام ۹ · حساب‌های آزمایشی بسازید**

localnet یک حساب دارای موجودی به نام `dispenser` دارد. با `algokit localnet dispenser` یا از طریق `algokit-utils` می‌توانید حساب‌های `alice` (فروشنده)، `bob` (خریدار) و `mallory` (مهاجم) را با موجودی بسازید. **این کلیدها فقط برای localnet هستند و هرگز نباید روی testnet یا mainnet استفاده شوند.**

**گام ۱۰ · اسکریپت deploy را اجرا کنید**

```bash
python scripts/deploy_localnet.py
```

اسکریپت باید این‌ها را چاپ کند: شناسه‌ی برنامه (App ID)، آدرس حساب قرارداد، و هش تأییدشده. هر مرحله با پیشوند `[deploy]` لاگ می‌شود.

**گام ۱۱ · تراکنش‌ها را در زنجیره ببینید**

```bash
algokit goal app read --app-id <APP_ID> --global   # وضعیت سراسری (localnet)
```

یا در مرورگر: `http://localhost:8980` (indexer). شناسه‌ی تراکنش را در آن جست‌وجو کنید.

### بخش د: تست (۷۰ تا ۸۵)

**گام ۱۲ · تست‌های قرارداد را اجرا کنید**

```bash
pytest -q tests/test_00_smoke.py   # ابتدا سلامت ابزارها
pytest -q tests/                  # سپس همه‌ی مراحل
```

تست‌ها باید این موارد را پوشش دهند: مسیر موفق، برداشت پیش از قفل، برداشت از وثیقه‌ی قفل‌شده، کد جعلی، کد قرارداد دیگر، پیش‌پرداخت بیرونی به آدرس قرارداد، حذف قرارداد، و رقابت دو تراکنش در یک بلوک.

**گام ۱۳ · یک تست خاص را اجرا کنید**

```bash
pytest -q tests/test_01_create.py -s --log-cli-level=DEBUG
```

پرچم `-s` لاگ‌های `print` و `log` را نشان می‌دهد.

### بخش هـ: دیباگ (۸۵ تا ۱۰۰)

**گام ۱۴ · لاگ‌های قرارداد را بخوانید**

قرارداد با `log(...)` رویداد ثبت می‌کند. هر خط با نام رویداد شروع می‌شود، پس می‌توانید فیلتر کنید:

```bash
algokit goal clerk dryrun ...        # شبیه‌سازی یک تراکنش بدون ثبت آن
algokit goal app read --app-id <ID>  # وضعیت فعلی
```

رویدادهای مهم: `EVENT:deposit`، `EVENT:locked`، `EVENT:code_verify`، `EVENT:settled`، `EVENT:delete_attempt`.

**گام ۱۵ · خطای `assert` را تفسیر کنید**

هر `assert` یک پیام دارد. آن پیام را در خروجی تراکنش رد‌شده پیدا کنید. اگر به شکل `logic eval error: assert failed` بود، پیام فارسی بالاتر همان دلیل است.

**گام ۱۶ · dry-run را برای خطایابی استفاده کنید**

قبل از ارسال واقعی، تراکنش را با dry-run امتحان کنید. این کار خطاهای منطقی را بدون هزینه نشان می‌دهد و از ارسال تراکنش ناقص جلوگیری می‌کند.

**گام ۱۷ · گزارش باگ بدهید**

برای گزارش، این موارد را بفرستید:

1. شماره‌ی گامی که خطا داد.
2. خروجی کامل ترمینال (بدون کلید خصوصی یا mnemonic).
3. `git rev-parse HEAD` و خروجی `algokit --version`.
4. هش برنامه‌ی کامپایل‌شده از گام ۷.

### بخش و: testnet (۱۰۰ و فراتر)

**گام ۱۸ · testnet را آماده کنید** *(فقط پس از موفقیت کامل localnet)*

- یک حساب testnet بسازید و با faucet موجودی بگیرید.
- **کلید خصوصی یا mnemonic را هرگز در مخزن یا فایل‌های تحت git ننویسید.** از KMD محلی یا کیف پول استفاده کنید.
- اسکریپت deploy را با `--network testnet` اجرا کنید (پس از افزودن این گزینه در مرحله‌ی بعد).

**گام ۱۹ · قبل از mainnet**

این قرارداد **حسابرسی نشده است.** پیش از هر استفاده روی mainnet باید حسابرسی امنیتی مستقل انجام شود.

---

## امنیت و تاریخچه‌ی مخزن

- **کلید خصوصی ناشر** پیش‌تر در `publisher_key.json` در این مخزن بود. این شاخه آن را از درخت فایل حذف کرده، اما **تاریخچه‌ی git هنوز آن را دارد.** چون مخزن عمومی است، آن کلید باید **فرض شود افشا شده است.** این کلید دیگر استفاده نمی‌شود، ولی اگر جایی به آن اعتماد شده باشد، باید باطل شود.
- برای پاک‌سازی تاریخچه از `git filter-repo` استفاده کنید و سپس کلید را باطل نگه دارید. این کار تاریخچه‌ی مشترک را تغییر می‌دهد و باید با همکاران هماهنگ شود.
- نسخه‌های `release.json` قبلی با کلید ناشر امضا شده بودند و در معماری جدید معتبر نیستند.

## مشکلات شناخته‌شده‌ی شبیه‌ساز قبلی

شبیه‌ساز در `legacy/simulator/` آرشیو شده است. مشکلات گزارش‌شده (KeyError در `PROGRAMS`، هش سورس پایتون، توقف `block_loop`، رقابت بررسی اعتبار طرف مقابل، پیش‌پرداخت به آدرس قرارداد و …) در معماری زنجیره‌ای از بین می‌روند یا باید در رابط بازبینی شوند. رابط `index.html` هنوز به زنجیره وصل نیست و این بخش‌ها در آن جداگانه پیگیری می‌شوند.

## محدودیت‌ها و هشدار

این نرم‌افزار **بدون هیچ ضمانتی** ارائه می‌شود. قرارداد حسابرسی نشده است. کاربر مسئول تصمیم‌ها و ریسک‌های مالی خود است. این مخزن مشاوره‌ی مالی یا حقوقی نیست. **هیچ‌گاه کلید خصوصی یا mnemonic واقعی را در مخزن قرار ندهید.**

## مجوز

Apache License 2.0. فایل `LICENSE` را ببینید.

---

<a id="english"></a>

## English

**Lmarket** is a peer-to-peer trade protocol on Algorand. Two parties who do not trust each other each lock an **equal** amount of collateral. Payment and delivery happen off-chain, and collateral is released only after **both confirmation codes** are recorded.

> **Status of this branch (`decentralized`):** the Python simulator and the publisher signing key have been removed from the tree. The smart contract is being written in PuyaPy and deployed to Algorand (localnet first, then testnet). **This branch does not yet contain the final contract**; it is built stage by stage and only **stage 1 (contract creation)** and **stage 2 (activation with `APP_FUND`)** are done. **Stage 3a (deposit and withdraw before lock)** is also done. **Stage 3b (exact-amount lock)** is also done: once both deposits reach the agreed amount, exactly that amount locks and only the surplus is withdrawable. **Stage 4a (`mark_paid`)** is also done; it is a declaration only and releases nothing. **Stage 4b (`mark_shipped`)** is also done (independent of `mark_paid`, declaration only). **Stage 4c (event timestamps)** is also done. **Stage 5a (Ed25519 public key registration)** and **stage 5a2 (key rotation)** are also done. There is still no confirmation code or settlement. See "Project status" below.

### Core ideas

- A smart contract has no physical power, so security comes from **economic incentives**. If a party does not fulfil its side, its own collateral stays locked.
- The contract does not judge the value, price, or fairness of a deal. The two parties set the collateral.
- No one can claim the other's collateral on their own word. The contract does not assign blame.
- **No admin, no upgrade path, no publisher key.** The approved program is immutable after deployment, and anyone can check its hash on-chain.

### Trade flow

| Step | Buyer (Bob) | Seller (Alice) |
|---|---|---|
| 1. Create and activate | Creates or activates the contract | Creates or activates the contract |
| 2. Deposit collateral | Deposits the agreed amount | Deposits the agreed amount |
| 3. Lock | Both collaterals lock once both deposits reach the amount | |
| 4. Pay and ship (off-chain) | Pays and records it | Ships and records it |
| 5. Confirm payment | Enters the seller's code | Generates the payment code |
| 6. Confirm delivery | Generates the delivery code | Enters the buyer's code |
| 7. Settlement | Both collaterals return once both codes are recorded | |

- If one party does not confirm, both collaterals stay locked. **There is no automatic timeout, by design.**
- A stated deadline is a reputation signal only; it never releases funds.

### Repository layout

```
lmarket/
├── README.md              # this file
├── LICENSE                # Apache-2.0
├── .gitignore
├── index.html             # demo UI; not yet connected to the chain
├── contracts/lmarket.py   # PuyaPy contract (stage 1)
├── config.py              # all settings (no environment variables)
├── scripts/               # deployment and helpers
├── tests/                 # contract tests on localnet
├── build/                 # puyapy output; not committed
└── legacy/simulator/      # archived Python simulator
```

---

## Project status (for continuing with another model or developer)

**Last verified state:** on Windows with AlgoKit localnet, `tests/test_00_smoke.py` (8 tests), `tests/test_01_create.py` (16 tests) and `tests/test_02_activate.py` (8 tests) `tests/test_03a_deposit.py` (14 tests) and `tests/test_03b_lock.py` (12 tests) `tests/test_04a_mark_paid.py` (10 tests) and `tests/test_04b_mark_shipped.py` (11 tests) and `tests/test_04c_timestamps.py` (7 tests) and `tests/test_05a_register_key.py` (10 tests) and `tests/test_05a2_rotate_key.py` (11 tests) are fully green (107 tests in total; run with `pytest -q`). Approval TEAL sha256 in that run: `4e21c1a458871b178e454064ba2f07c3980c035dc07127b53888a8564e324ebd`.

**Versions it worked with:** AlgoKit 2.10.2, puyapy 5.10.1, algorand-python 4.0.0, py-algorand-sdk 2.12.0, pytest 9.2.0, Python **3.12** inside the venv (the global Python is 3.15 and must not be used for this project), algod 5.1.1 on localnet.

### Stages

| Stage | Content | Status |
|---|---|---|
| 0 | Tooling health (algod, accounts, TEAL compile) | done, green |
| 1 | `create` and input validation, immutable program | done, green |
| 2 | Activation with the base balance payment (`APP_FUND`) | done, green |
| 3a | `deposit` and `withdraw` before lock, counterparty deposit visible | done, green |
| 3b | Exact-amount lock, free and withdrawable surplus | done, green |
| 4a | `mark_paid` by the buyer | done, green |
| 4b | `mark_shipped` by the seller | done, green |
| 4c | record the time of activation, lock, paid and shipped (`activated_at`, `locked_at`, `paid_at`, `shipped_at`); record-only | done, green |
| 5a | `register_key`: each party's Ed25519 public key, once, with time; record-only | done, green |
| 5a2 | `rotate_key`, with time and rotation counter; freezing a key after its code is recorded comes in 5d | done, green |
| 5 | Confirmation code as an Ed25519 signature (`ed25519verify_bare`) over a message bound to the app id | |
| 6 | Settlement and deletion | |
| 7 | Adversarial tests: forged code, code from another contract, pre-funding the contract address, two transactions racing in one block | |

Each stage adds a few lines to the contract and its own tests. The next stage starts only when the previous tests are green.

### Design rules (from the project agreement)

- No admin, no upgrade, no publisher key. Integrity is checked by the hash of the compiled TEAL, not the Python source.
- Before lock, each party can withdraw at any time. When both deposits reach the agreed amount, **exactly that amount** is locked from each side; the surplus stays free and withdrawable.
- No collateral is released before **both** confirmation codes are recorded. The deadline (`due_secs`) is informational and never releases funds.
- A confirmation code must be the counterparty's Ed25519 signature over a message bound to the app id, so it cannot be replayed in another contract.
- The contract stays neutral and has no right to intervene. Reputation (open contracts, duration, wallet age) is left to the market; the UI only warns.

### Working rules for the code

- **Terminal output (prints, test assertion messages, logs) must be in English.** Comments, docstrings and docs stay Persian.
- Settings live only in `config.py`, not environment variables. The constants at the top of `contracts/lmarket.py` must match `config.py` (`test_constants_match` checks this).
- All py-algorand-sdk calls live in `tests/helpers.py`, so an SDK version change touches one file.
- Each rejection test proves two things: it was rejected, and for the expected assert message (`helpers.rejected`). Each rejection also has a passing "witness" with valid input.
- Contract assert messages are English and must survive in the TEAL as comments (`test_teal_keeps_assert_messages`).
- After every contract change: `python scripts/build.py`, then `pytest`. Record the new hash.

### Known issues and open work

- After 4c the global state holds 13 uints and 3 byte slices (9 uints before). After 5a2: 17 uints and 5 byte slices (`GLOBAL_UINTS` temporarily 24). `GLOBAL_UINTS` and `GLOBAL_BYTES` in `config.py` are currently larger than needed. At the end, replace them with exact numbers, because every extra slot raises the creator's minimum balance.
- There is still **no test for pre-funding the contract address** (before it exists) and no same-block race test; both arrive in stage 7.
- `index.html` is not connected to the chain and still depends on the old `release.json` and `algosim`. It must be rewritten to read the TEAL hash from the chain.
- This repository has not been security audited. Do not use it on mainnet without an independent audit.
- The old publisher private key is still in git history; treat it as compromised (see "Security and repository history").
- Commit `822ed8e` still carries the email `claude@anthropic.com` (cosmetic only).

### Quick check of the current state (Windows, `(.venv)` active, localnet running)

```powershell
git pull
python scripts/build.py
pytest -q tests/test_00_smoke.py
pytest -q tests/test_01_create.py
```

---

## Step-by-step guide: 0 to 100 (compile, deploy, debug)

> **Honesty note:** these commands follow the official AlgoKit and PuyaPy documentation but have not yet been verified on a development machine. If a step fails, save the **full terminal output** together with the step number. That report is the best input for fixing this guide.

### Part A: setup (0–30)

**Step 0 · Check prerequisites**
- Docker Desktop is installed and **running** (localnet requires it).
- Python 3.12 is installed: `python3 --version` (Windows: `py -3.12 --version`). **Do not use Python 3.13 or 3.15 for this project** unless PuyaPy officially supports it.
- On Windows, `algokit doctor` may report Node.js and Poetry as missing. This project does not need them and you can ignore those lines.
- Git is installed: `git --version`

**Step 1 · Get the repository**
```bash
git clone https://github.com/UsaCapitalist/Lmarket.git
cd Lmarket
git checkout decentralized
```

**Step 2 · Create a virtual environment**
```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
# Windows (PowerShell): you must pick 3.12 explicitly; the default python may be 3.15
py -3.12 -m venv .venv
# if activate says "running scripts is disabled" (this window only):
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
python -m pip install --upgrade pip
```

**Step 3 · Install AlgoKit CLI**
```bash
python -m pip install --user pipx
python -m pipx ensurepath
# close and reopen the terminal, then:
pipx install algokit
algokit --version
algokit doctor
```
`algokit doctor` should confirm Docker, Python and Git. Fix whichever check fails.

**Step 4 · Install project packages**
```bash
pip install -r requirements.txt
puyapy --version
```

**Step 5 · Start localnet** (the first run takes several minutes)
```bash
algokit localnet start
algokit localnet status
```
`status` should show algod, indexer and KMD running. Default algod URL: `http://localhost:4001`.

### Part B: compile (30–50)

**Step 6 · Compile the contract**
```bash
python scripts/build.py
# معادل دستی: puyapy --out-dir build contracts/lmarket.py
```
Expected output: `*.approval.teal` and `*.clear.teal` (the TEAL programs), `*.arc56.json` (ABI description) and `*.puya.map` (source maps).

**Important:** after `activate` the prompt must start with `(.venv)`. Without it `pytest` and `puyapy` are not found.

**Step 7 · Record the program hash**
The hash of the **compiled** program (not the Python source) determines what runs. Save it; the front end will check it against the chain.
```bash
python -c "import hashlib; print(hashlib.sha256(open('build/Lmarket.approval.teal','rb').read()).hexdigest())"
```

**Step 8 · Read compile errors**
- `puyapy` errors point to a file, line and column. Look at that line in `contracts/lmarket.py`.
- For type errors (e.g. `UInt64` vs `int`), wrap the value in `UInt64(...)` or use `arc4.UInt64`.
- A successful compile does not prove the logic is correct; that is what the tests are for.

### Part C: deploy to localnet (50–70)

**Step 9 · Create test accounts**
Localnet has a funded `dispenser` account. Use `algokit localnet dispenser` or `algokit-utils` to create `alice` (seller), `bob` (buyer) and `mallory` (attacker) with balances. **These keys are for localnet only and must never be used on testnet or mainnet.**

**Step 10 · Run the deploy script**
```bash
python scripts/deploy_localnet.py
```
It should print the App ID, the application address and the approval-program hash. Each step logs with a `[deploy]` prefix.

**Step 11 · Inspect the chain**
```bash
algokit goal app read --app-id <APP_ID> --global
```
Or open the indexer at `http://localhost:8980` and search for the transaction ID.

### Part D: test (70–85)

**Step 12 · Run the contract tests**
```bash
pytest -q tests/test_00_smoke.py   # tool health first
pytest -q tests/                  # then every stage
```
Tests must cover: the happy path; withdrawing before lock; withdrawing from locked collateral; forged codes; a code from another contract; an off-chain payment sent to the contract address; deleting a contract; and two transactions competing in the same block.

**Step 13 · Run one test with output**
```bash
pytest -q tests/test_01_create.py -s --log-cli-level=DEBUG
```
The `-s` flag shows `print` and `log` output.

### Part E: debug (85–100)

**Step 14 · Read contract logs**
The contract emits `log(...)` events, each starting with an event name, so you can filter for them. Important events: `EVENT:deposit`, `EVENT:locked`, `EVENT:code_verify`, `EVENT:settled`, `EVENT:delete_attempt`.

**Step 15 · Interpret an `assert` failure**
Each `assert` carries a message. Find it in the rejected transaction's output. A line like `logic eval error: assert failed` is followed by the message, which names the cause.

**Step 16 · Use dry-run before real submission**
Simulate a transaction before sending it. This shows logic errors without committing anything to the chain.

**Step 17 · File a bug report**
Include: the step number, the full terminal output (never a private key or mnemonic), `git rev-parse HEAD`, `algokit --version`, and the program hash from Step 7.

### Part F: testnet (100 and beyond)

**Step 18 · Prepare testnet** *(only after localnet passes fully)*
- Create a testnet account and fund it from the faucet.
- **Never write a private key or mnemonic into the repository or any git-tracked file.** Use KMD or a wallet.
- Run the deploy script with `--network testnet` (once that option is added in the next step).

**Step 19 · Before mainnet**
This contract **has not been audited.** Before any mainnet use, an independent security audit is required.

---

## Security and repository history

- **The publisher private key** was previously committed as `publisher_key.json`. This branch removes it from the tree, but **git history still contains it.** Because the repository is public, treat that key as **compromised**. It is no longer used, but anything that trusted it must be revoked.
- To purge history, use `git filter-repo`, then keep the key revoked. This rewrites shared history and must be coordinated with collaborators.
- Earlier `release.json` files were signed with that key and are invalid under the new design.

## Known issues in the old simulator

The simulator is archived in `legacy/simulator/`. Its reported issues (the `PROGRAMS` KeyError, the source-based program hash, the unguarded `block_loop`, the counterparty-check race, pre-funding of the contract address, and others) either disappear with on-chain execution or must be fixed in the UI. `index.html` is not yet connected to the chain, and these items are tracked separately.

## Disclaimer

This software is provided **as is**, without warranty of any kind. The contract has not been audited. You are responsible for your own financial decisions and risks. Nothing in this repository is financial or legal advice. **Never commit a real private key or mnemonic.**

## License

Apache License 2.0. See `LICENSE`.
