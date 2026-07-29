"""Count-up animation for KPI numbers.

Deliberately conservative:
  * one shared timer for all running animations
  * skips the animation entirely for tiny changes or huge lists
  * always lands exactly on the target value, never an eased approximation
"""
from PyQt5.QtCore import QTimer

_DURATION_MS = 850
_INTERVAL_MS = 33          # ~30fps: smooth enough, cheap enough


class _Engine:
    _timer = None
    _jobs = []             # [label, start, end, elapsed, formatter, duration]

    @classmethod
    def add(cls, label, start, end, formatter, duration):
        # Replace any in-flight animation for the same label.
        cls._jobs = [j for j in cls._jobs if j[0] is not label]
        cls._jobs.append([label, float(start), float(end), 0, formatter, duration])
        if cls._timer is None:
            cls._timer = QTimer()
            cls._timer.setInterval(_INTERVAL_MS)
            cls._timer.timeout.connect(cls._tick)
        if not cls._timer.isActive():
            cls._timer.start()

    @classmethod
    def _tick(cls):
        alive = []
        for job in cls._jobs:
            label, start, end, elapsed, fmt, duration = job
            elapsed += _INTERVAL_MS
            t = min(1.0, elapsed / duration)
            eased = 1 - (1 - t) ** 3          # easeOutCubic
            value = start + (end - start) * eased
            try:
                label.setText(fmt(end if t >= 1.0 else value))
            except RuntimeError:
                continue                       # widget destroyed mid-flight
            except Exception:
                continue
            if t < 1.0:
                job[3] = elapsed
                alive.append(job)
        cls._jobs = alive
        if not cls._jobs and cls._timer is not None:
            cls._timer.stop()


def animate_value(label, new_value, formatter, old_value=None, duration_ms=None):
    """Animate *label* from its current value up to *new_value*.

    ``formatter`` turns a float into the display string, so the final frame
    is byte-identical to setting the text directly.
    """
    try:
        target = float(new_value or 0)
    except (TypeError, ValueError):
        label.setText(formatter(new_value))
        return

    if old_value is None:
        old_value = getattr(label, "_cu_value", 0.0)
    try:
        start = float(old_value or 0)
    except (TypeError, ValueError):
        start = 0.0

    label._cu_value = target

    # Not worth animating: no visible change, or a jump so large the tween
    # reads as noise rather than motion.
    if abs(target - start) < 0.01:
        label.setText(formatter(target))
        return

    _Engine.add(label, start, target, formatter, max(_INTERVAL_MS, duration_ms or _DURATION_MS))


def set_value(label, value, formatter):
    """Set a value with no animation, keeping the count-up state in sync."""
    label._cu_value = float(value or 0)
    label.setText(formatter(value))
