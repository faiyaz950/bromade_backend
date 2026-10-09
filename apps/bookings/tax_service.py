from decimal import ROUND_HALF_UP, Decimal

TWOPLACES = Decimal('0.01')
TAX_RATE = Decimal('0.05')


class TaxService:
    @staticmethod
    def calculate_tax(taxable_amount, rate=TAX_RATE):
        """Return (rate, tax_amount) for a post-discount taxable amount."""
        amount = (Decimal(taxable_amount) * rate).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        return rate, amount
