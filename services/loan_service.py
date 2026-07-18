"""Loan service — EMI formula, amortization."""


class LoanService:
    @staticmethod
    def emi(principal, rate_pct, months):
        if rate_pct == 0 or months == 0:
            return round(principal / months, 2) if months else 0
        r = rate_pct / 12 / 100
        return round(principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1), 2)

    @staticmethod
    def amortize(principal, rate_pct, months):
        emi_val = LoanService.emi(principal, rate_pct, months)
        r = rate_pct / 12 / 100
        bal = principal
        out = []
        for m in range(1, months + 1):
            interest = bal * r
            prin = emi_val - interest
            bal = max(bal - prin, 0)
            out.append({"month": m, "emi": emi_val, "principal": round(prin, 2),
                        "interest": round(interest, 2), "balance": round(bal, 2)})
        return out
