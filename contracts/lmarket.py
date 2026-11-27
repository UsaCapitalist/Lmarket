"""
Lmarket — سفته‌ی دیجیتال روی Algorand (PuyaPy)

===== مرحله‌ی ۱: ساخت قرارداد و اعتبارسنجی ورودی‌ها =====
در این مرحله فقط این‌ها وجود دارد:
  * متد create: طرفین، مبلغ توافقی و مهلت را ثبت می‌کند.
  * هیچ متد update/delete/opt-in وجود ندارد؛ پس برنامه تغییرناپذیر است.
واریز، قفل، کد تأیید و تسویه در مراحل بعد اضافه می‌شوند.

===== مرحله‌ی ۴پ: زمان وقوع رویدادها =====
برای اعتبارسنجی در لایه‌های بالاتر، زمان هر رویداد مهم (فعال‌سازی، قفل، پرداخت، ارسال) در حافظه‌ی
قرارداد ثبت می‌شود. زمان‌ها فقط ثبت‌اند و هیچ منطق مالی به آن‌ها وابسته نیست. پرچم‌های قبلی
(activated, locked, paid, shipped) بدون تغییر می‌مانند. زمان از Global.latest_timestamp می‌آید
(ثانیه؛ تقریبی و در حد چند ثانیه دقیق، مناسب مقیاس ساعت و روز، نه ساعت دقیق).

===== مرحله‌ی ۵الف: ثبت کلید عمومی Ed25519 =====
هر طرف (خریدار یا فروشنده) پس از فعال‌سازی، یک‌بار کلید عمومی خودش (۳۲ بایت) را همراه زمان ثبت می‌کند.
فقط ثبت است: هنوز هیچ امضایی بررسی نمی‌شود (۵پ و ۵ت) و تعویض کلید در ۵الف۲ می‌آید.
کلید پیش از ثبت اصلاً در حافظه نیست؛ «ثبت‌شده بودن» را فیلد *_key_at (۰ = ثبت نشده) نشان می‌دهد.

===== مرحله‌ی ۵الف۲: تعویض کلید =====
هر طرف می‌تواند کلید ثبت‌شده‌ی خودش را با کلید تازه عوض کند (کلید قبلی منسوخ می‌شود). *_key_at زمان
کلید فعلی و *_key_n تعداد تعویض‌هاست (برای اعتبارسنجی). محدودیت تعداد وجود ندارد و تعویض فقط
اعلام است. قفل‌شدن کلید پس از ثبت کدی که با آن امضا شده، همراه ثبت کد (۵ث) می‌آید.

قاعده‌ها (از توافق پروژه):
  * بدون مدیر و بدون امکان به‌روزرسانی.
  * فقط خریدار یا فروشنده می‌تواند قرارداد بسازد.
  * مهلت (due_secs) فقط اطلاع‌رسانی است و هرگز وجهی را آزاد نمی‌کند.
"""

from algopy import Account, ARC4Contract, Bytes, Global, GlobalState, Txn, UInt64, arc4, gtxn, itxn, log

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
        (مرحله‌ی ۳الف: هنوز قفلی وجود ندارد؛ قفل در ۳ب می‌آید.)
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
        else:
            self.seller_dep.value = dep - amount.native

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
            assert self.buyer_key.value != key.native, "new key must differ"
            self.buyer_key.value = key.native
            self.buyer_key_at.value = Global.latest_timestamp
            self.buyer_key_n.value += UInt64(1)
        else:
            assert self.seller_key_at.value != UInt64(0), "key not registered"
            assert self.seller_key.value != key.native, "new key must differ"
            self.seller_key.value = key.native
            self.seller_key_at.value = Global.latest_timestamp
            self.seller_key_n.value += UInt64(1)

        log("EVENT:key_rotated")
