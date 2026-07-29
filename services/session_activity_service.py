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

    def summary(self):
        lines=[]
        for (module, action, obj, source, detail), count in self._events.most_common():
            noun=obj if count==1 else (obj+'es' if obj.endswith('s') else obj+'s')
            suffix=f" from {source}" if source and source != module else ''
            extra=f" ({detail})" if detail else ''
            lines.append(f"{count} {noun} {action}{suffix}{extra}")
        return lines
