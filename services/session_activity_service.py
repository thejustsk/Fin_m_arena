"""Explicit, user-facing session activity journal for the exit summary."""
from collections import Counter

class SessionActivityService:
    def __init__(self):
        self._events = Counter()

    def log(self, module, action, object_type, source=None, detail=None):
        """Record one successful user action after its database commit."""
        self._events[(module, action, object_type, source or module, detail or '')] += 1

    def has_events(self):
        return bool(self._events)

    def covered_fallback_nouns(self):
        """Generic SQL nouns replaced by explicit domain wording."""
        mapping = {
            'regular transaction': 'regular transaction', 'transfer': 'transfer transaction',
            'note': 'note', 'budget': 'budget', 'split expense': 'split expense',
            'split settlement': 'split settlement', 'credit card': 'credit card',
            'debit card': 'debit card', 'account': 'account',
        }
        return {mapping.get(obj) for _, _, obj, _, _ in self._events if mapping.get(obj)}

    def summary(self):
        lines=[]
        for (module, action, obj, source, detail), count in self._events.most_common():
            noun=obj if count==1 else (obj+'es' if obj.endswith('s') else obj+'s')
            suffix=f" from {source}" if source else ''
            extra=f" ({detail})" if detail else ''
            lines.append(f"{count} {noun} {action}{suffix}{extra}")
        return lines
