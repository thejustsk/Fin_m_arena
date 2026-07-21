"""Loan service — EMI formula, amortization, loan analysis."""
from datetime import date as _date


class LoanService:
    # ── compounding helpers ──────────────────────────────────────────
    @staticmethod
    def _monthly_rate(annual_pct, frequency="ANNUAL"):
        """Effective monthly rate from annual rate and compounding frequency."""
        r = annual_pct / 100
        if r == 0:
            return 0.0
        if frequency == "QUARTERLY":
            return (1 + r / 4) ** (1 / 3) - 1
        if frequency == "SEMI_ANNUAL":
            return (1 + r / 2) ** (1 / 6) - 1
        # ANNUAL (default)
        return (1 + r) ** (1 / 12) - 1

    # ── EMI ──────────────────────────────────────────────────────────
    @staticmethod
    def emi(principal, rate_pct, months, frequency="ANNUAL"):
        if months == 0:
            return 0.0
        if rate_pct == 0:
            return round(principal / months, 2)
        r = LoanService._monthly_rate(rate_pct, frequency)
        if r == 0:
            return round(principal / months, 2)
        return round(principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1), 2)

    # ── total expected repayment ─────────────────────────────────────
    @staticmethod
    def total_expected(emi_val, months):
        return round(emi_val * months, 2)

    # ── amortization schedule ────────────────────────────────────────
    @staticmethod
    def amortize(principal, rate_pct, months, frequency="ANNUAL"):
        emi_val = LoanService.emi(principal, rate_pct, months, frequency)
        r = LoanService._monthly_rate(rate_pct, frequency)
        bal = principal
        out = []
        for m in range(1, months + 1):
            interest = bal * r
            prin = emi_val - interest
            bal = max(bal - prin, 0)
            out.append({"month": m, "emi": emi_val, "principal": round(prin, 2),
                        "interest": round(interest, 2), "balance": round(bal, 2)})
        return out

    # ── full loan analysis (reducing balance) ────────────────────────
    @staticmethod
    def loan_analysis(principal, rate_pct, months, frequency, total_paid,
                      start_date, as_of_date=None):
        """
        Reducing-balance analysis as of *as_of_date*.

        Returns dict with:
            current_value   – what the loan has become (outstanding + unpaid interest)
            original_emi    – EMI at origination
            updated_emi     – EMI recalculated on current_value for remaining tenure
            full_payoff     – amount to close the loan today
            total_expected  – original_emi × months
            total_paid      – actual payments so far
            months_elapsed  – completed months since start
            months_remaining
            total_interest_accrued
        """
        if as_of_date is None:
            as_of_date = _date.today()
        if isinstance(start_date, str):
            start_date = _date.fromisoformat(start_date)
        if isinstance(as_of_date, str):
            as_of_date = _date.fromisoformat(as_of_date)

        r = LoanService._monthly_rate(rate_pct, frequency)
        emi_val = LoanService.emi(principal, rate_pct, months, frequency)

        # months elapsed (capped)
        elapsed = (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month)
        elapsed = max(0, min(elapsed, months))
        remaining = max(months - elapsed, 0)

        # simulate amortization for elapsed months → expected balance
        bal = principal
        total_interest = 0.0
        for _ in range(elapsed):
            interest = bal * r
            total_interest += interest
            prin_part = emi_val - interest
            bal = max(bal - prin_part, 0)

        # adjust for actual vs expected payments
        expected_paid = emi_val * elapsed
        overpayment = total_paid - expected_paid
        current_value = max(bal - overpayment, 0)

        # full payoff = everything owed right now
        full_payoff = max(current_value, 0)

        # updated EMI on remaining balance for remaining tenure
        if remaining > 0 and current_value > 0:
            updated_emi = LoanService.emi(current_value, rate_pct, remaining, frequency)
        else:
            updated_emi = 0.0

        return {
            "current_value": round(current_value, 2),
            "original_emi": round(emi_val, 2),
            "updated_emi": round(updated_emi, 2),
            "full_payoff": round(full_payoff, 2),
            "total_expected": round(emi_val * months, 2),
            "total_paid": round(total_paid, 2),
            "months_elapsed": elapsed,
            "months_remaining": remaining,
            "total_interest_accrued": round(total_interest, 2),
        }
