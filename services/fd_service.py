"""FD service — maturity calc (quarterly compounding)."""
from datetime import datetime


class FDService:
    @staticmethod
    def maturity(principal, rate_pct, start_str, mat_str):
        s = datetime.strptime(start_str, "%Y-%m-%d")
        m = datetime.strptime(mat_str, "%Y-%m-%d")
        years = (m - s).days / 365.25
        return round(principal * ((1 + rate_pct / 400) ** (4 * years)), 2)

    @staticmethod
    def progress(start_str, mat_str):
        s = datetime.strptime(start_str, "%Y-%m-%d")
        m = datetime.strptime(mat_str, "%Y-%m-%d")
        total = (m - s).days
        elapsed = (datetime.now() - s).days
        return min(max(elapsed / total * 100, 0), 100) if total > 0 else 0
