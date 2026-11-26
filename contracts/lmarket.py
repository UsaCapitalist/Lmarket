"""
Lmarket — سفته‌ی دیجیتال روی Algorand (PuyaPy)

===== مرحله‌ی ۱: ساخت قرارداد و اعتبارسنجی ورودی‌ها =====
در این مرحله فقط این‌ها وجود دارد:
  * متد create: طرفین، مبلغ توافقی و مهلت را ثبت می‌کند.
  * هیچ متد update/delete/opt-in وجود ندارد؛ پس برنامه تغییرناپذیر است.
واریز، قفل، کد تأیید و تسویه در مراحل بعد اضافه می‌شوند.

قاعده‌ها (از توافق پروژه):
  * بدون مدیر و بدون امکان به‌روزرسانی.
  * فقط خریدار یا فروشنده می‌تواند قرارداد بسازد.
  * مهلت (due_secs) فقط اطلاع‌رسانی است و هرگز وجهی را آزاد نمی‌کند.
"""

from algopy import Account, ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, log

# ثابت‌ها: باید با config.py یکی باشند (تست test_constants_match بررسی می‌کند).
MIN_AGREED = 100_000        # microAlgo
MIN_DUE_SECS = 3_600
MAX_DUE_SECS = 31_536_000


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

        log("EVENT:created")
