# Lmarket · سفته‌ی دیجیتال / Digital Promissory Note

[فارسی](#فارسی) · [English](#english)

---

<a id="فارسی"></a>

## فارسی

**ال مارکت** یک پروتکل معامله‌ی شخص به شخص روی Algorand است. دو طرفی که به هم اعتماد شخصی ندارند، هر کدام وثیقه‌ای به **مبلغ برابر** قفل می‌کنند. پرداخت و تحویل کالا بیرون از زنجیره انجام می‌شود و وثیقه‌ها فقط پس از ثبت **هر دو کد تأیید** آزاد می‌شوند.

> **وضعیت این شاخه (`decentralized`):** شبیه‌ساز پایتون و کلید امضای ناشر از مخزن حذف شده‌اند. قرارداد هوشمند به‌صورت PuyaPy نوشته و روی Algorand (ابتدا localnet، سپس testnet) مستقر می‌شود. این شاخه هنوز **قرارداد نهایی ندارد**؛ فایل `contracts/lmarket.py` در مرحله‌ی بعد نوشته می‌شود.

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
├── contracts/             # قرارداد PuyaPy (در مرحله‌ی بعد)
├── scripts/               # deploy و ابزارهای کمکی
├── tests/                 # تست‌های قرارداد روی localnet
├── build/                 # خروجی puyapy؛ در git نیست
└── legacy/simulator/      # شبیه‌ساز قدیمی پایتون (فقط آرشیو)
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

> **Status of this branch (`decentralized`):** the Python simulator and the publisher signing key have been removed from the tree. The smart contract is being written in PuyaPy and deployed to Algorand (localnet first, then testnet). **This branch does not yet contain the final contract**; `contracts/lmarket.py` is the next step.

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
├── contracts/             # PuyaPy contract (next step)
├── scripts/               # deployment and helpers
├── tests/                 # contract tests on localnet
├── build/                 # puyapy output; not committed
└── legacy/simulator/      # archived Python simulator
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
