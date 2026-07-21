"""Loan service — EMI formula, amortization, loan analysis (simple + compound)."""
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
        return (1 + r) ** (1 / 12) - 1

    # ── simple interest ──────────────────────────────────────────────
    @staticmethod
    def simple_interest(principal, rate_pct, months):
        """Simple interest accrued over *months*."""
        return round(principal * rate_pct / 100 * months / 12, 2)

    @staticmethod
    def simple_emi(principal, rate_pct, months):
        """Flat EMI under simple interest: (principal + total_interest) / months."""
        if months == 0:
            return 0.0
        total_interest = LoanService.simple_interest(principal, rate_pct, months)
        return round((principal + total_interest) / months, 2)

    # ── compound EMI ─────────────────────────────────────────────────
    @staticmethod
    def compound_emi(principal, rate_pct, months, frequency="ANNUAL"):
        if months == 0:
            return 0.0
        if rate_pct == 0:
            return round(principal / months, 2)
        r = LoanService._monthly_rate(rate_pct, frequency)
        if r == 0:
            return round(principal / months, 2)
        return round(principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1), 2)

    # ── generic EMI dispatcher ───────────────────────────────────────
    @staticmethod
    def emi(principal, rate_pct, months, frequency="ANNUAL", method="COMPOUND"):
        if method == "SIMPLE":
            return LoanService.simple_emi(principal, rate_pct, months)
        return LoanService.compound_emi(principal, rate_pct, months, frequency)

    # ── total expected repayment ─────────────────────────────────────
    @staticmethod
    def total_expected(emi_val, months):
        return round(emi_val * months, 2)

    # ── amortization schedule (compound only) ────────────────────────
    @staticmethod
    def amortize(principal, rate_pct, months, frequency="ANNUAL"):
        emi_val = LoanService.compound_emi(principal, rate_pct, months, frequency)
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

    # ── full loan analysis ───────────────────────────────────────────
    @staticmethod
    def loan_analysis(principal, rate_pct, months, frequency, total_paid,
                      start_date, as_of_date=None, method="COMPOUND", payments=None):
        """
        Reducing-balance (compound) or flat (simple) analysis as of *as_of_date*.
        """
        if method == "SIMPLE":
            return LoanService._simple_analysis(
                principal, rate_pct, months, total_paid, start_date, as_of_date)
        return LoanService._compound_analysis(
            principal, rate_pct, months, frequency, total_paid, start_date, as_of_date,
            payments=payments)

    # ── compound (reducing balance) ──────────────────────────────────
    @staticmethod
    def _compound_analysis(principal, rate_pct, months, frequency, total_paid,
                           start_date, as_of_date=None, payments=None):
        if as_of_date is None:
            as_of_date = _date.today()
        if isinstance(start_date, str):
            start_date = _date.fromisoformat(start_date)
        if isinstance(as_of_date, str):
            as_of_date = _date.fromisoformat(as_of_date)

        r = LoanService._monthly_rate(rate_pct, frequency)
        emi_val = LoanService.compound_emi(principal, rate_pct, months, frequency)

        elapsed = (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month)
        elapsed = max(0, min(elapsed, months))
        remaining = max(months - elapsed, 0)

        bal = principal
        total_interest = 0.0
        for _ in range(elapsed):
            interest = bal * r
            total_interest += interest
            prin_part = emi_val - interest
            bal = max(bal - prin_part, 0)

        expected_paid = emi_val * elapsed
        overpayment = total_paid - expected_paid
        current_value = max(bal - overpayment, 0)

        if remaining > 0 and current_value > 0:
            updated_emi = LoanService.compound_emi(current_value, rate_pct, remaining, frequency)
        else:
            updated_emi = 0.0

        return {
            "current_value": round(current_value, 2),
            "original_emi": round(emi_val, 2),
            "updated_emi": round(updated_emi, 2),
            "full_payoff": round(max(current_value, 0), 2),
            "total_expected": round(emi_val * months, 2),
            "total_paid": round(total_paid, 2),
            "months_elapsed": elapsed,
            "months_remaining": remaining,
            "total_interest_accrued": round(total_interest, 2),
        }

    # ── simple (flat) ────────────────────────────────────────────────
    @staticmethod
    def _simple_analysis(principal, rate_pct, months, total_paid,
                         start_date, as_of_date=None):
        if as_of_date is None:
            as_of_date = _date.today()
        if isinstance(start_date, str):
            start_date = _date.fromisoformat(start_date)
        if isinstance(as_of_date, str):
            as_of_date = _date.fromisoformat(as_of_date)

        elapsed = (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month)
        elapsed = max(0, min(elapsed, months))
        remaining = max(months - elapsed, 0)

        total_interest = LoanService.simple_interest(principal, rate_pct, months)
        interest_till_now = LoanService.simple_interest(principal, rate_pct, elapsed)

        emi_val = LoanService.simple_emi(principal, rate_pct, months)

        # current value = principal + interest accrued so far - payments made
        current_value = max(principal + interest_till_now - total_paid, 0)

        # updated EMI: remaining amount / remaining months
        if remaining > 0 and current_value > 0:
            updated_emi = round(current_value / remaining, 2)
        else:
            updated_emi = 0.0

        return {
            "current_value": round(current_value, 2),
            "original_emi": round(emi_val, 2),
            "updated_emi": round(updated_emi, 2),
            "full_payoff": round(max(current_value, 0), 2),
            "total_expected": round(principal + total_interest, 2),
            "total_paid": round(total_paid, 2),
            "months_elapsed": elapsed,
            "months_remaining": remaining,
            "total_interest_accrued": round(interest_till_now, 2),
        }

    # ── non-EMI analysis (variable repayment, no fixed schedule) ────
    @staticmethod
    def non_emi_analysis(principal, rate_pct, total_paid, start_date,
                         payments=None, as_of_date=None, method="SIMPLE"):
        if as_of_date is None:
            as_of_date = _date.today()
        if isinstance(start_date, str):
            start_date = _date.fromisoformat(start_date)
        if isinstance(as_of_date, str):
            as_of_date = _date.fromisoformat(as_of_date)
        elapsed = (as_of_date.year - start_date.year) * 12 + (as_of_date.month - start_date.month)
        elapsed = max(0, elapsed)

        if method == "SIMPLE":
            # Simple interest: flat on original principal
            interest = round(principal * rate_pct / 100 * elapsed / 12, 2)
            current_value = max(principal + interest - total_paid, 0)
        else:
            # Compound: simulate month-by-month with actual payments
            r = LoanService._monthly_rate(rate_pct, "ANNUAL")
            bal = float(principal)
            total_interest = 0.0
            for m in range(elapsed):
                month_start = _date(start_date.year + (start_date.month + m - 1) // 12,
                                    (start_date.month + m - 1) % 12 + 1, 1)
                month_end_y = start_date.year + (start_date.month + m) // 12
                month_end_m = (start_date.month + m) % 12 + 1
                month_end = _date(month_end_y, month_end_m, 1)
                mi, me = month_start.isoformat(), month_end.isoformat()
                int_m = bal * r
                total_interest += int_m
                if payments:
                    mp = sum(p["amount_paid"] for p in payments if mi <= p["payment_date"] < me)
                    bal = max(bal + int_m - mp, 0)
                else:
                    bal = bal + int_m
            current_value = max(bal, 0)
            interest = round(total_interest, 2)

        return {
            "current_value": round(current_value, 2), "original_emi": 0, "updated_emi": 0,
            "full_payoff": round(current_value, 2), "total_expected": round(principal + interest, 2),
            "total_paid": round(total_paid, 2), "total_interest_accrued": interest,
            "months_elapsed": elapsed, "months_remaining": 0,
        }

    # ── plan amortization for a given outstanding ────────────────────
    @staticmethod
    def plan_amortization(outstanding, rate_pct, months, frequency="ANNUAL", method="COMPOUND"):
        if method == "SIMPLE":
            return LoanService._simple_schedule(outstanding, rate_pct, months)
        return LoanService.amortize(outstanding, rate_pct, months, frequency)

    @staticmethod
    def _simple_schedule(outstanding, rate_pct, months):
        if months <= 0:
            return []
        int_per_month = round(outstanding * rate_pct / 100 / 12, 2) if rate_pct > 0 else 0
        emi = round((outstanding + int_per_month * months) / months, 2)
        bal = outstanding
        rows = []
        for m in range(1, months + 1):
            prin = round(emi - int_per_month, 2)
            bal = max(bal - prin, 0)
            rows.append({"month": m, "emi": emi, "principal": prin,
                         "interest": int_per_month, "balance": round(bal, 2)})
        return rows
