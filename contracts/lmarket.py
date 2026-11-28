"""
Lmarket — سفته‌ی دیجیتال روی Algorand (PuyaPy)

===== مرحله‌ی ۱: ساخت قرارداد و اعتبارسنجی ورودی‌ها =====
در این مرحله فقط این‌ها وجود دارد:
  * متد create: طرفین، مبلغ توافقی و مهلت را ثبت می‌کند.
  * هیچ متد update/delete/opt-in وجود ندارد؛ پس برنامه تغییرناپذیر است.
واریز، قفل، کد تأیید و تسویه در مراحل بعد اضافه می‌شوند.

===== مرحله‌ی 4c: زمان وقوع رویدادها =====
برای اعتبارسنجی در لایه‌های بالاتر، زمان هر رویداد مهم (فعال‌سازی، قفل، پرداخت، ارسال) در حافظه‌ی
قرارداد ثبت می‌شود. زمان‌ها فقط ثبت‌اند و هیچ منطق مالی به آن‌ها وابسته نیست. پرچم‌های قبلی
(activated, locked, paid, shipped) بدون تغییر می‌مانند. زمان از Global.latest_timestamp می‌آید
(ثانیه؛ تقریبی و در حد چند ثانیه دقیق، مناسب مقیاس ساعت و روز، نه ساعت دقیق).

===== مرحله‌ی 5a: ثبت کلید عمومی Ed25519 =====
هر طرف (خریدار یا فروشنده) پس از فعال‌سازی، یک‌بار کلید عمومی خودش (۳۲ بایت) را همراه زمان ثبت می‌کند.
فقط ثبت است: هنوز هیچ امضایی بررسی نمی‌شود (5b و 5c) و تعویض کلید در 5a2 می‌آید.
کلید پیش از ثبت اصلاً در حافظه نیست؛ «ثبت‌شده بودن» را فیلد *_key_at (۰ = ثبت نشده) نشان می‌دهد.

===== مرحله‌ی 5a2: تعویض کلید =====
هر طرف می‌تواند کلید ثبت‌شده‌ی خودش را با کلید تازه عوض کند (کلید قبلی منسوخ می‌شود). *_key_at زمان
کلید فعلی و *_key_n تعداد تعویض‌هاست (برای اعتبارسنجی). محدودیت تعداد وجود ندارد و تعویض فقط
اعلام است. قفل‌شدن کلید پس از ثبت کدی که با آن امضا شده، همراه ثبت کد (5d) می‌آید.

===== مرحله‌ی 5b: ساخت پیام امضا =====
متد فقط‌خواندنی message(role) پیامی را برمی‌گرداند که هر طرف برای کد تأیید امضا می‌کند. قالب و دلیل هر فیلد
در tests/signing_message.py آمده است؛ همه‌ی مقدارها از حافظه‌ی خود قرارداد (نه ورودی کاربر) می‌آیند.
فقط پس از قفل تعریف‌شده است.

===== مرحله‌ی 5c: بررسی امضای کد تأیید =====
متد verify_code(role, sig) فقط درستی امضا را می‌سنجد (ed25519verify_bare روی همان پیام 5b با کلید ثبت‌شده‌ی
امضاکننده: نقش ۱ = کلید فروشنده، نقش ۲ = کلید خریدار) و اگر نادرست باشد رد می‌شود. هیچ حالتی تغییر
نمی‌کند و هیچ پولی جابه‌جا نمی‌شود؛ ثبت کد در 5d می‌آید. ساخت پیام در یک تابع مشترک است تا پیام
بررسی‌شده همیشه با خروجی message() یکی باشد. بودجه‌ی اجرا (۱۹۰۰ واحد برای بررسی امضا) با
ensure_budget تأمین می‌شود و کارمزد تراکنش‌های کمکی را فراخواننده می‌پردازد (گروه‌اعتبار).

===== مرحله‌ی 5d: ثبت کد تأیید =====
متد submit_code(role, sig) کد امضاشده‌ی یک طرف را، توسط طرف مقابل، ثبت می‌کند: خریدار کد فروشنده (نقش ۱) و
فروشنده کد خریدار (نقش ۲) را. امضا با همان بررسی 5c سنجیده می‌شود. هر نقش فقط یک‌بار ثبت می‌شود و فقط
زمان ثبت می‌ماند (خود امضا نه). ترتیب نسبت به mark_paid و mark_shipped آزاد است. پس از ثبت کد، کلید امضاکننده
قفل می‌شود (rotate_key رد می‌شود). هنوز هیچ وجهی آزاد نمی‌شود؛ تسویه در 6a می‌آید.

===== مرحله‌ی 5f: رکورد ساختاریافته‌ی برداشت =====
هر withdraw موفق علاوه بر log قبلی، یک رکورد با قالب ثابت log می‌کند (EVENT:withdrawn_v1 + برداشت‌کننده + مبلغ
+ زمان + قفل‌بودن + واریزی طرف مقابل + واریزی باقی‌مانده). برای اعتبارسنجی است: برداشت پس از واریز کامل طرف
مقابل و پیش از قفل نشانه‌ی معطل‌کردن است. هیچ قاعده‌ی مالی عوض نمی‌شود.

===== مرحله‌ی 5e: ثبت طرفِ تکمیل‌کننده‌ی قفل =====
در لحظه‌ی قفل، فرستنده‌ی واریزی که قفل را کامل کرد در locked_by ثبت می‌شود (خریدار یا فروشنده). فقط ثبت است و
هیچ قاعده‌ی مالی به آن وابسته نیست؛ برای اعتبارسنجی می‌گوید کدام طرف زمان قفل را به تأخیر انداخته است.

قاعده‌ها (از توافق پروژه):
  * بدون مدیر و بدون امکان به‌روزرسانی.
  * فقط خریدار یا فروشنده می‌تواند قرارداد بسازد.
  * مهلت (due_secs) فقط اطلاع‌رسانی است و هرگز وجهی را آزاد نمی‌کند.
"""

from algopy import (
    Account,
    ARC4Contract,
    Bytes,
    Global,
    GlobalState,
    OpUpFeeSource,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
)

# ثابت‌ها: باید با config.py یکی باشند (تست test_constants_match بررسی می‌کند).
MIN_AGREED = 100_000        # microAlgo
MIN_DUE_SECS = 3_600
MAX_DUE_SECS = 31_536_000
APP_FUND = 1_200_000        # microAlgo؛ پرداخت فعال‌سازی برای حداقل موجودی حساب قرارداد


class Lmarket(ARC4Contract):
    def __init__(self) -> None:
        # هویت طرف‌ها
        self.creator = GlobalState(Account)
        self.buyer = GlobalState(Account)
        self.seller = GlobalState(Account)
        # مبلغ توافقی و زمان‌بندی
        self.agreed = GlobalState(UInt64)
        self.due_secs = GlobalState(UInt64)
        self.created_at = GlobalState(UInt64)
        # ۰ = هنوز فعال نشده، ۱ = فعال شده (پرداخت APP_FUND ثبت شده)
        self.activated = GlobalState(UInt64)
        # واریزی هر طرف (microAlgo)؛ برای هر دو طرف قابل خواندن است
        self.buyer_dep = GlobalState(UInt64)
        self.seller_dep = GlobalState(UInt64)
        # ۰ = قفل نشده، ۱ = از هر طرف دقیقاً agreed قفل شده (یک‌طرفه؛ برگشت ندارد)
        self.locked = GlobalState(UInt64)
        # ۱ = خریدار پرداخت بیرون‌زنجیره را ثبت کرده (فقط اطلاع‌رسانی؛ هیچ وجهی را آزاد نمی‌کند)
        self.paid = GlobalState(UInt64)
        # ۱ = فروشنده ارسال را ثبت کرده (فقط اطلاع‌رسانی؛ مستقل از paid و بدون آزادسازی وجه)
        self.shipped = GlobalState(UInt64)
        # زمان وقوع هر رویداد (ثانیه‌ی یونیکس)؛ ۰ = هنوز رخ نداده. فقط ثبت‌اند و منطقی به آن‌ها وابسته نیست.
        self.activated_at = GlobalState(UInt64)
        self.locked_at = GlobalState(UInt64)
        self.paid_at = GlobalState(UInt64)
        self.shipped_at = GlobalState(UInt64)
        # کلید عمومی Ed25519 هر طرف (۳۲ بایت) و زمان ثبت آن؛ *_key_at = ۰ یعنی هنوز ثبت نشده
        # (خود کلید تا پیش از ثبت در حافظه وجود ندارد)
        self.buyer_key = GlobalState(Bytes)
        self.seller_key = GlobalState(Bytes)
        self.buyer_key_at = GlobalState(UInt64)
        self.seller_key_at = GlobalState(UInt64)
        # تعداد دفعاتی که هر طرف کلیدش را عوض کرده (ثبت اول حساب نمی‌شود)
        self.buyer_key_n = GlobalState(UInt64)
        self.seller_key_n = GlobalState(UInt64)
        # زمان ثبت کد هر طرف (۰ = هنوز ثبت نشده): seller_code_at = کد فروشنده (نقش ۱)، buyer_code_at = کد خریدار (نقش ۲)
        self.seller_code_at = GlobalState(UInt64)
        self.buyer_code_at = GlobalState(UInt64)
        # طرفی که با واریزش قفل را کامل کرد (برای اعتبارسنجی: چه کسی طرف مقابل را در انتظار نگه داشت)؛
        # تا پیش از قفل در حافظه وجود ندارد
        self.locked_by = GlobalState(Account)

    @arc4.abimethod(create="require")
    def create(
        self,
        buyer: arc4.Address,
        seller: arc4.Address,
        agreed: arc4.UInt64,
        due_secs: arc4.UInt64,
    ) -> None:
        log("EVENT:create_attempt")

        assert buyer.native != seller.native, "buyer and seller must differ"
        assert (
            Txn.sender == buyer.native or Txn.sender == seller.native
        ), "only buyer or seller may create"
        assert agreed.native >= MIN_AGREED, "agreed below minimum"
        assert due_secs.native >= MIN_DUE_SECS, "due_secs below minimum"
        assert due_secs.native <= MAX_DUE_SECS, "due_secs above maximum"

        self.creator.value = Txn.sender
        self.buyer.value = buyer.native
        self.seller.value = seller.native
        self.agreed.value = agreed.native
        self.due_secs.value = due_secs.native
        self.created_at.value = Global.latest_timestamp
        self.activated.value = UInt64(0)
        self.buyer_dep.value = UInt64(0)
        self.seller_dep.value = UInt64(0)
        self.locked.value = UInt64(0)
        self.paid.value = UInt64(0)
        self.shipped.value = UInt64(0)
        self.activated_at.value = UInt64(0)
        self.locked_at.value = UInt64(0)
        self.paid_at.value = UInt64(0)
        self.shipped_at.value = UInt64(0)
        self.buyer_key_at.value = UInt64(0)
        self.seller_key_at.value = UInt64(0)
        self.buyer_key_n.value = UInt64(0)
        self.seller_key_n.value = UInt64(0)
        self.seller_code_at.value = UInt64(0)
        self.buyer_code_at.value = UInt64(0)

        log("EVENT:created")

    @arc4.abimethod
    def activate(self, pay: gtxn.PaymentTransaction) -> None:
        """
        فعال‌سازی: سازنده با پرداختی به‌اندازه‌ی دقیق APP_FUND به حساب قرارداد،
        حداقل موجودی لازم برای نگه‌داری حالت سراسری را تأمین می‌کند. فقط یک‌بار.
        """
        log("EVENT:activate_attempt")

        assert self.activated.value == UInt64(0), "already activated"
        assert Txn.sender == self.creator.value, "only creator may activate"
        assert pay.sender == self.creator.value, "payment sender must be creator"
        assert pay.receiver == Global.current_application_address, "payment must go to the contract"
        assert pay.amount == APP_FUND, "activation payment must equal APP_FUND"

        self.activated.value = UInt64(1)
        self.activated_at.value = Global.latest_timestamp

        log("EVENT:activated")

    @arc4.abimethod
    def deposit(self, pay: gtxn.PaymentTransaction) -> None:
        """
        واریز: خریدار یا فروشنده مبلغی به حساب قرارداد می‌فرستد و به واریزی خودش اضافه می‌شود.
        (مرحله‌ی 3a: هنوز قفلی وجود ندارد؛ قفل در 3b می‌آید.)
        """
        log("EVENT:deposit_attempt")

        assert self.activated.value == UInt64(1), "contract not activated"
        assert (
            Txn.sender == self.buyer.value or Txn.sender == self.seller.value
        ), "only buyer or seller may deposit"
        assert pay.sender == Txn.sender, "deposit payment sender must be the caller"
        assert pay.receiver == Global.current_application_address, "deposit must go to the contract"
        assert pay.amount > UInt64(0), "deposit must be positive"

        if Txn.sender == self.buyer.value:
            self.buyer_dep.value += pay.amount
        else:
            self.seller_dep.value += pay.amount

        # با رسیدن واریزی هر دو طرف به مبلغ توافقی، دقیقاً agreed از هر طرف قفل می‌شود؛
        # مازاد آزاد می‌ماند (قفل یک پرچم است، نه جابه‌جایی پول)
        if (
            self.locked.value == UInt64(0)
            and self.buyer_dep.value >= self.agreed.value
            and self.seller_dep.value >= self.agreed.value
        ):
            self.locked.value = UInt64(1)
            self.locked_at.value = Global.latest_timestamp
            self.locked_by.value = Txn.sender
            log("EVENT:locked")

        log("EVENT:deposited")

    @arc4.abimethod
    def withdraw(self, amount: arc4.UInt64) -> None:
        """
        برداشت: هر طرف فقط از واریزی خودش و فقط به آدرس خودش برمی‌دارد؛ پس از قفل فقط از مازاد.
        کارمزد تراکنش داخلی صفر است و فراخواننده کارمزد دو تراکنش را می‌پردازد.
        """
        log("EVENT:withdraw_attempt")

        assert (
            Txn.sender == self.buyer.value or Txn.sender == self.seller.value
        ), "only buyer or seller may withdraw"
        assert amount.native > UInt64(0), "withdraw must be positive"

        if Txn.sender == self.buyer.value:
            dep = self.buyer_dep.value
        else:
            dep = self.seller_dep.value
        assert amount.native <= dep, "withdraw exceeds deposit"
        # پس از قفل، فقط مازاد بر agreed آزاد است (dep >= agreed از لحظه‌ی قفل همیشه برقرار است)
        if self.locked.value == UInt64(1):
            assert amount.native <= dep - self.agreed.value, "withdraw exceeds free balance"

        # ابتدا حالت به‌روز می‌شود، سپس پول فرستاده می‌شود
        if Txn.sender == self.buyer.value:
            self.buyer_dep.value = dep - amount.native
            who = Bytes(b"B")
            other_dep = self.seller_dep.value
        else:
            self.seller_dep.value = dep - amount.native
            who = Bytes(b"S")
            other_dep = self.buyer_dep.value

        # رکورد ساختاریافته‌ی برداشت (5f) برای اعتبارسنجی؛ قالب ثابت، پس از پیشوند ۱۸بایتی:
        # برداشت‌کننده(1: B خریدار / S فروشنده) | مبلغ(8) | زمان(8) | قفل‌بودن(1) | واریزی طرف مقابل(8) | واریزی باقی‌مانده‌ی خودش(8)
        log(
            Bytes(b"EVENT:withdrawn_v1"),
            who,
            op.itob(amount.native),
            op.itob(Global.latest_timestamp),
            op.extract(op.itob(self.locked.value), UInt64(7), UInt64(1)),
            op.itob(other_dep),
            op.itob(dep - amount.native),
        )

        itxn.Payment(receiver=Txn.sender, amount=amount.native, fee=0).submit()

        log("EVENT:withdrawn")

    @arc4.abimethod
    def mark_paid(self) -> None:
        """
        ثبت پرداخت: فقط خریدار، فقط پس از قفل و فقط یک‌بار.
        این ثبت صرفاً اعلام است؛ هیچ پولی جابه‌جا و هیچ وثیقه‌ای آزاد نمی‌شود.
        """
        log("EVENT:mark_paid_attempt")

        assert Txn.sender == self.buyer.value, "only buyer may mark paid"
        assert self.locked.value == UInt64(1), "mark paid requires lock"
        assert self.paid.value == UInt64(0), "already marked paid"

        self.paid.value = UInt64(1)
        self.paid_at.value = Global.latest_timestamp

        log("EVENT:paid")

    @arc4.abimethod
    def mark_shipped(self) -> None:
        """
        ثبت ارسال: فقط فروشنده، فقط پس از قفل و فقط یک‌بار.
        ترتیب آن نسبت به mark_paid اجباری نیست (بیرون از زنجیره هر ترتیبی ممکن است).
        صرفاً اعلام است؛ هیچ پولی جابه‌جا و هیچ وثیقه‌ای آزاد نمی‌شود.
        """
        log("EVENT:mark_shipped_attempt")

        assert Txn.sender == self.seller.value, "only seller may mark shipped"
        assert self.locked.value == UInt64(1), "mark shipped requires lock"
        assert self.shipped.value == UInt64(0), "already marked shipped"

        self.shipped.value = UInt64(1)
        self.shipped_at.value = Global.latest_timestamp

        log("EVENT:shipped")

    @arc4.abimethod
    def register_key(self, key: arc4.DynamicBytes) -> None:
        """
        ثبت کلید عمومی Ed25519: هر طرف فقط برای خودش، فقط پس از فعال‌سازی و فقط یک‌بار.
        صرفاً ثبت است؛ هیچ پولی جابه‌جا نمی‌شود و هیچ امضایی بررسی نمی‌شود.
        """
        log("EVENT:register_key_attempt")

        assert self.activated.value == UInt64(1), "contract not activated"
        assert (
            Txn.sender == self.buyer.value or Txn.sender == self.seller.value
        ), "only buyer or seller may register key"
        assert key.native.length == UInt64(32), "key must be 32 bytes"

        if Txn.sender == self.buyer.value:
            assert self.buyer_key_at.value == UInt64(0), "key already registered"
            self.buyer_key.value = key.native
            self.buyer_key_at.value = Global.latest_timestamp
        else:
            assert self.seller_key_at.value == UInt64(0), "key already registered"
            self.seller_key.value = key.native
            self.seller_key_at.value = Global.latest_timestamp

        log("EVENT:key_registered")

    @arc4.abimethod
    def rotate_key(self, key: arc4.DynamicBytes) -> None:
        """
        تعویض کلید: هر طرف فقط کلید خودش را، فقط پس از ثبت اول، و فقط با کلیدی متفاوت از کلید فعلی.
        کلید قبلی منسوخ می‌شود؛ زمان کلید فعلی به‌روز و شمارنده‌ی تعویض یکی زیاد می‌شود.
        """
        log("EVENT:rotate_key_attempt")

        assert (
            Txn.sender == self.buyer.value or Txn.sender == self.seller.value
        ), "only buyer or seller may rotate key"
        assert key.native.length == UInt64(32), "key must be 32 bytes"

        if Txn.sender == self.buyer.value:
            assert self.buyer_key_at.value != UInt64(0), "key not registered"
            assert self.buyer_code_at.value == UInt64(0), "key frozen after code"
            assert self.buyer_key.value != key.native, "new key must differ"
            self.buyer_key.value = key.native
            self.buyer_key_at.value = Global.latest_timestamp
            self.buyer_key_n.value += UInt64(1)
        else:
            assert self.seller_key_at.value != UInt64(0), "key not registered"
            assert self.seller_code_at.value == UInt64(0), "key frozen after code"
            assert self.seller_key.value != key.native, "new key must differ"
            self.seller_key.value = key.native
            self.seller_key_at.value = Global.latest_timestamp
            self.seller_key_n.value += UInt64(1)

        log("EVENT:key_rotated")

    @arc4.abimethod(readonly=True)
    def message(self, role: arc4.UInt8) -> arc4.DynamicBytes:
        """
        پیام امضا برای کد تأیید (طول ثابت ۱۵۵ بایت؛ قالب در tests/signing_message.py).
        نقش: ۱ = فروشنده دریافت وجه را تأیید می‌کند، ۲ = خریدار دریافت کالا را تأیید می‌کند.
        همه‌ی مقدارها از حافظه‌ی قرارداد می‌آیند و فقط پس از قفل تعریف می‌شود؛ هیچ حالتی تغییر نمی‌کند.
        """
        assert self.locked.value == UInt64(1), "message requires lock"
        assert role.native == UInt64(1) or role.native == UInt64(2), "invalid role"

        return arc4.DynamicBytes(self._build_message(role.native))

    @subroutine
    def _build_message(self, role: UInt64) -> Bytes:
        """پیام امضا (قالب در tests/signing_message.py)؛ تنها منبع ساخت پیام، برای message() و بررسی امضا."""
        return (
            Bytes(b"LMARKET-V1")
            + op.extract(op.itob(role), UInt64(7), UInt64(1))
            + Global.genesis_hash
            + op.itob(Global.current_application_id.id)
            + self.buyer.value.bytes
            + self.seller.value.bytes
            + op.itob(self.agreed.value)
            + op.itob(self.due_secs.value)
            + op.itob(self.created_at.value)
            + op.itob(self.activated_at.value)
            + op.itob(self.locked_at.value)
        )

    @subroutine
    def _verify(self, role: UInt64, sig: Bytes) -> None:
        """درستی امضای کد تأیید را می‌سنجد؛ نقش ۱ با کلید فروشنده و نقش ۲ با کلید خریدار."""
        ensure_budget(UInt64(2500), OpUpFeeSource.GroupCredit)

        assert self.locked.value == UInt64(1), "message requires lock"
        assert role == UInt64(1) or role == UInt64(2), "invalid role"

        if role == UInt64(1):
            assert self.seller_key_at.value != UInt64(0), "signer key not registered"
            key = self.seller_key.value
        else:
            assert self.buyer_key_at.value != UInt64(0), "signer key not registered"
            key = self.buyer_key.value
        assert sig.length == UInt64(64), "signature must be 64 bytes"

        assert op.ed25519verify_bare(self._build_message(role), sig, key), "invalid signature"

    @arc4.abimethod
    def verify_code(self, role: arc4.UInt8, sig: arc4.DynamicBytes) -> None:
        """
        بررسی امضای کد تأیید (5c): فقط می‌سنجد و رد یا قبول می‌کند؛ حالتی را تغییر نمی‌دهد.
        هر کسی می‌تواند فراخوانی کند (برای پیش‌بررسی در رابط). کارمزد باید بودجه‌ی اضافی را بپوشاند.
        """
        log("EVENT:verify_code_attempt")

        self._verify(role.native, sig.native)

        log("EVENT:code_verified")

    @arc4.abimethod
    def submit_code(self, role: arc4.UInt8, sig: arc4.DynamicBytes) -> None:
        """
        ثبت کد تأیید (5d): طرف مقابل کد امضاشده را می‌فرستد؛ خریدار کد فروشنده (نقش ۱) و فروشنده کد خریدار (نقش ۲).
        فقط یک‌بار برای هر نقش، فقط زمان ثبت می‌شود و هیچ پولی جابه‌جا نمی‌شود. کارمزد باید بودجه‌ی اضافی را بپوشاند.
        """
        log("EVENT:submit_code_attempt")

        assert role.native == UInt64(1) or role.native == UInt64(2), "invalid role"
        if role.native == UInt64(1):
            assert Txn.sender == self.buyer.value, "only buyer may submit seller code"
            assert self.seller_code_at.value == UInt64(0), "code already submitted"
        else:
            assert Txn.sender == self.seller.value, "only seller may submit buyer code"
            assert self.buyer_code_at.value == UInt64(0), "code already submitted"

        self._verify(role.native, sig.native)

        if role.native == UInt64(1):
            self.seller_code_at.value = Global.latest_timestamp
        else:
            self.buyer_code_at.value = Global.latest_timestamp

        log("EVENT:code_recorded")
