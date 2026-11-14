# Lmarket · سفته‌ی دیجیتال / Digital Promissory Note

[فارسی](#فارسی) · [English](#english)

---

<a id="فارسی"></a>

## فارسی

**ال مارکت** یک پروتکل معامله‌ی شخص به شخص روی شبکه‌ی Algorand است. دو نفر که به یکدیگر اعتماد شخصی ندارند، هر کدام وثیقه‌ای به مقدار برابر قفل می‌کنند. پرداخت و تحویل کالا خارج از بلاکچین انجام می‌شود، و وثیقه‌ها تنها پس از تأیید متقابل هر دو طرف آزاد می‌شوند.

### ایده‌ی اصلی

- قرارداد هوشمند هیچ قدرت فیزیکی ندارد؛ پس امنیت را با **انگیزه‌ی اقتصادی** تضمین می‌کند. اگر طرفی تعهد خود را انجام ندهد، وثیقه‌ی خودش قفل می‌ماند.
- قرارداد ارزش کالا، قیمت، یا عادلانه بودن معامله را تعیین نمی‌کند. مقدار وثیقه را دو طرف تعیین می‌کنند.
- قرارداد درباره‌ی شخص مقصر قضاوت نمی‌کند و هیچ‌کس نمی‌تواند تنها با ادعای خود، وثیقه‌ی طرف مقابل را بردارد.
- هدف، ساختن یک **سفته‌ی دیجیتال** ساده است؛ یک بلوک پایه که بتوان روی آن سیستم‌های پیچیده‌تر ساخت.

### جریان معامله

| مرحله | خریدار (Bob) | فروشنده (Alice) |
|---|---|---|
| ۱. قفل وثیقه | قفل وثیقه‌ی توافق‌شده | قفل وثیقه‌ی توافق‌شده |
| ۲. پرداخت و ارسال (خارج از زنجیره) | پرداخت وجه | ارسال کالا |
| ۳. تأیید دریافت وجه | کد فروشنده را وارد می‌کند | دریافت وجه را تأیید و کد می‌سازد |
| ۴. تأیید دریافت کالا | دریافت کالا را تأیید و کد می‌سازد | کد خریدار را وارد می‌کند |
| ۵. تسویه | وثیقه‌ها پس از ثبت هر دو کد آزاد می‌شوند | |

اگر یکی از طرفین تأیید نکند، وثیقه‌ی خودش قفل می‌ماند. قرارداد پایه مهلت زمانی ندارد؛ این رفتار عمدی است.

### نسخه‌ی فعلی

این مخزن در حال حاضر یک **رابط کاربری نمایشی** است (فایل `lmarket.html`).

- بدون سرور، بدون وابستگی به بسته‌ی نصبی؛ کافی است فایل را در مرورگر باز کنید.
- همه‌ی تنظیمات در ابتدای بخش `<script>` و در شیء `CONFIG` قرار دارد. متغیر محیطی لازم نیست.
- اتصال به کیف پول، ساخت قرارداد و خواندن وضعیت از بلاکچین هنوز پیاده‌سازی نشده‌اند و با `TODO` علامت‌گذاری شده‌اند.
- کدهای تأیید فعلاً در صفحه تولید می‌شوند. در نسخه‌ی روی زنجیره باید به‌صورت هش (commitment) در قرارداد ذخیره شوند.

### اجرا

```bash
# روش ۱: دوبار کلیک روی فایل lmarket.html
# روش ۲: میزبانی روی GitHub Pages یا Cloudflare Workers
```

برای اتصال به شبکه‌ی واقعی، در شیء `CONFIG` مقدار `demo` را `false` کنید و پیاده‌سازی `TODO`ها را کامل کنید. پیش از استفاده روی mainnet، حتماً روی testnet آزمایش کنید.

### هشدار

این نرم‌افزار بدون هیچ ضمانتی ارائه می‌شود. قرارداد هنوز حسابرسی نشده است. کاربر مسئول تصمیم‌ها و ریسک‌های مالی خود است. این مخزن مشاوره‌ی مالی یا حقوقی نیست.

### مجوز

این پروژه تحت مجوز **Apache License 2.0** منتشر شده است. فایل `LICENSE` را ببینید.

---

<a id="english"></a>

## English

**Lmarket** is a peer-to-peer trade protocol on the Algorand network. Two people who do not need to trust each other each lock an equal amount of collateral. Payment and delivery happen outside the blockchain, and the collateral is released only after both parties confirm.

### Core idea

- A smart contract has no physical power, so security comes from **economic incentives**. If a party does not fulfil its side, its own collateral stays locked.
- The contract does not determine the value of the goods, the price, or whether the deal is fair. The two parties choose the collateral amount.
- The contract does not judge who is at fault, and no one can claim the other's collateral based only on their own statement.
- The goal is a simple **digital promissory note**: a base primitive on which more complex systems can be built.

### Trade flow

| Step | Buyer (Bob) | Seller (Alice) |
|---|---|---|
| 1. Lock collateral | Lock the agreed collateral | Lock the agreed collateral |
| 2. Pay and ship (off-chain) | Send payment | Ship the goods |
| 3. Confirm payment | Enter the code from the seller | Confirm payment and generate a code |
| 4. Confirm delivery | Confirm receipt and generate a code | Enter the code from the buyer |
| 5. Settlement | Collateral is released once both codes are recorded | |

If one party does not confirm, its own collateral remains locked. The base contract has no timeout; this is intentional.

### Current state

This repository currently contains a **demo user interface** (`lmarket.html`).

- No server and no build step; open the file in a browser.
- All settings are at the top of the `<script>` block in the `CONFIG` object. No environment variables are needed.
- Wallet connection, contract creation, reading state from the chain, and confirmation calls are not implemented yet. They are marked `TODO` in the code.
- Confirmation codes are currently generated in the page. The on-chain version should store them as hash commitments in the contract.

### Running it

```bash
# Option 1: double-click lmarket.html
# Option 2: host it on GitHub Pages or Cloudflare Workers
```

To connect to a real network, set `demo` to `false` in `CONFIG` and complete the `TODO` items. Test on testnet before using mainnet.

### Disclaimer

This software is provided **as is**, without warranty of any kind. The contract has not been audited. You are responsible for your own financial decisions and risks. Nothing in this repository is financial or legal advice.

### License

Licensed under the **Apache License, Version 2.0**. See the `LICENSE` file for details.
