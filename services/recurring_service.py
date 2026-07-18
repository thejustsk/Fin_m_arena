"""Recurring service — remind and confirm, never auto-post."""
from datetime import datetime


class RecurringService:
    def __init__(self, recurring_repo):
        self.repo = recurring_repo

    def get_due(self):
        """Return rules where next_run_date <= today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return [r for r in self.repo.list_active() if r["next_run_date"] <= today]
