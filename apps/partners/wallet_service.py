from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.partners.models import PartnerProfile, WalletTransaction

COMMISSION_RATE = Decimal('0.30')
_MONEY = Decimal('0.01')


def money(value) -> Decimal:
    return Decimal(value).quantize(_MONEY, rounding=ROUND_HALF_UP)


def commission_amount(job_amount) -> Decimal:
    return money(Decimal(job_amount) * COMMISSION_RATE)


def inr(value) -> str:
    quantized = money(value)
    text = f'{quantized:.2f}'
    if text.endswith('.00'):
        text = text[:-3]
    return f'₹{text}'


class InsufficientWalletError(ValueError):
    def __init__(self, *, wallet_balance, required_amount, job_amount):
        self.wallet_balance = money(wallet_balance)
        self.required_amount = money(required_amount)
        self.job_amount = money(job_amount)
        self.shortfall = money(self.required_amount - self.wallet_balance)
        super().__init__(
            f'Low wallet balance. This {inr(self.job_amount)} job needs '
            f'{inr(self.required_amount)} (30%) in your wallet to accept. '
            f'Current wallet: {inr(self.wallet_balance)}. '
            f'Pay Bayti and ask admin to add the amount.'
        )


class WalletService:
    @staticmethod
    def credit(*, partner: PartnerProfile, amount, note: str = '', created_by=None) -> WalletTransaction:
        credit_amount = money(amount)
        if credit_amount <= 0:
            raise ValueError('Wallet credit must be greater than zero.')
        with transaction.atomic():
            locked = PartnerProfile.objects.select_for_update().get(pk=partner.pk)
            locked.wallet_balance = money(locked.wallet_balance) + credit_amount
            locked.save(update_fields=['wallet_balance', 'updated_at'])
            txn = WalletTransaction.objects.create(
                partner=locked,
                entry_type=WalletTransaction.EntryType.CREDIT,
                amount=credit_amount,
                balance_after=locked.wallet_balance,
                note=note[:255],
                created_by=created_by,
            )
            partner.wallet_balance = locked.wallet_balance
            return txn

    @staticmethod
    def debit_commission(*, partner: PartnerProfile, booking) -> WalletTransaction:
        required = commission_amount(booking.total_amount)
        with transaction.atomic():
            locked = PartnerProfile.objects.select_for_update().get(pk=partner.pk)
            balance = money(locked.wallet_balance)
            if balance < required:
                raise InsufficientWalletError(
                    wallet_balance=balance,
                    required_amount=required,
                    job_amount=booking.total_amount,
                )
            locked.wallet_balance = balance - required
            locked.save(update_fields=['wallet_balance', 'updated_at'])
            txn = WalletTransaction.objects.create(
                partner=locked,
                entry_type=WalletTransaction.EntryType.DEBIT,
                amount=required,
                balance_after=locked.wallet_balance,
                note=f'30% commission for {inr(booking.total_amount)} job',
                booking=booking,
            )
            partner.wallet_balance = locked.wallet_balance
            return txn
