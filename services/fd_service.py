"""FD service — maturity calc with configurable compounding."""
from datetime import datetime


class FDService:
    @staticmethod
    def maturity(principal, rate_pct, start_str, mat_str, frequency="QUARTERLY"):
        s = datetime.strptime(start_str, "%Y-%m-%d")
        m = datetime.strptime(mat_str, "%Y-%m-%d")
        years = (m - s).days / 365.25
        periods_per_year = {"ANNUAL": 1, "SEMI_ANNUAL": 2, "QUARTERLY": 4}.get(frequency, 4)
        r = rate_pct / (100 * periods_per_year)
        n = periods_per_year * years
        return round(principal * ((1 + r) ** n), 2)

    @staticmethod
    def progress(start_str, mat_str):
        s = datetime.strptime(start_str, "%Y-%m-%d")
        m = datetime.strptime(mat_str, "%Y-%m-%d")
        total = (m - s).days
        elapsed = (datetime.now() - s).days
        return min(max(elapsed / total * 100, 0), 100) if total > 0 else 0
