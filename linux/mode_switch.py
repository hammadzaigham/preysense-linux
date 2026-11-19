"""Apply the first performance-mode request and coalesce the rest while the EC settles."""
import math
import time

from PySide6.QtCore import QObject, QTimer, Qt

VALID_MODES = frozenset((0, 1, 4, 5, 6))
SETTLE_MS = 2000
LIGHTING_RESTORE_MS = 1550


class ModeSwitch(QObject):
    def __init__(self, callback, parent=None, clock=time.monotonic):
        super().__init__(parent)
        if not callable(callback):
            raise TypeError('Mode callback must be callable')
        self.callback = callback
        self.clock = clock
        self._pending = None
        self._deadline = None
        self._last_sent = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.flush)

    @property
    def pending(self):
        return self._pending

    def _now(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('Mode timer requires a finite monotonic clock')
        return now

    def _dispatch(self, mode, now):
        self._pending = None
        self._last_sent = mode
        self._deadline = now + SETTLE_MS / 1000
        self.timer.start(SETTLE_MS)
        self.callback(mode)

    def request(self, mode):
        if type(mode) is not int or mode not in VALID_MODES:
            raise ValueError('Unsupported performance mode')
        now = self._now()
        if self._deadline is None:
            self._dispatch(mode, now)
        else:
            self._pending = mode

    def cancel(self):
        self.timer.stop()
        self._pending = self._deadline = self._last_sent = None

    def flush(self):
        if self._deadline is None:
            return
        now = self._now()
        remaining = self._deadline - now
        if remaining > 0:
            self.timer.start(max(1, math.ceil(remaining * 1000)))
        elif self._pending is None or self._pending == self._last_sent:
            self.cancel()
        else:
            self._dispatch(self._pending, now)
