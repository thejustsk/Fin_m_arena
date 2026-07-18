"""Visualization service — prepares data for Chart.js."""


class VisualizationService:
    @staticmethod
    def category_breakdown(transactions):
        """Returns (labels, data, colors) for category doughnut."""
        cats = {}
        for t in transactions:
            if t["tx_type"] == "DEBIT":
                name = t.get("cat_name") or "Other"
                cats[name] = cats.get(name, 0) + t["amount"]
        labels = list(cats.keys())
        data = [round(v, 2) for v in cats.values()]
        colors = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
                  '#EC4899', '#06B6D4', '#F97316', '#6366F1', '#14B8A6']
        return labels, data, colors[:len(labels)]

    @staticmethod
    def pf_breakdown(transactions):
        """Returns (labels, data) for PF category horizontal bar."""
        pfs = {}
        for t in transactions:
            if t["tx_type"] == "DEBIT":
                pf = (t.get("pf_category") or "nc").replace("_", " ").title()
                pfs[pf] = pfs.get(pf, 0) + t["amount"]
        return list(pfs.keys()), [round(v, 2) for v in pfs.values()]
