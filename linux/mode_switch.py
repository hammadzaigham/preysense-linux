"""Debounce explicit performance-mode requests without delaying other actions."""
import math
import time
from PySide6.QtCore import QObject, QTimer, Qt

VALID_MODES=frozenset((0,1,4,5,6))
DEBOUNCE_SECONDS=1.0


class ModeSwitch(QObject):
    """Call callback once after a full second without a new manual request.

    The owner must route only manual performance selection here. Editor Apply,
    automatic source policies retain their immediate paths.
    Construct and use on the owning Qt thread. No hardware access occurs here.
    """
    def __init__(self,callback,parent=None,clock=time.monotonic):
        super().__init__(parent)
        if not callable(callback):raise TypeError('Mode callback must be callable')
        self.callback=callback
        self.clock=clock
        self._pending=None
        self._deadline=None
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.flush)

    @property
    def pending(self):return self._pending

    def _now(self):
        now=self.clock()
        if isinstance(now,bool) or not isinstance(now,(int,float)) or not math.isfinite(now):
            raise ValueError('Mode timer requires a finite monotonic clock')
        return now

    def request(self,mode):
        if type(mode) is not int or mode not in VALID_MODES:
            raise ValueError('Unsupported performance mode')
        now=self._now()
        self._pending=mode
        self._deadline=now+DEBOUNCE_SECONDS
        self.timer.start(1000)

    def cancel(self):
        self.timer.stop()
        self._pending=None
        self._deadline=None

    def flush(self):
        """Deliver only at/after the deadline, even if Qt wakes early."""
        if self._pending is None:return
        remaining=self._deadline-self._now()
        if remaining>0:
            self.timer.start(max(1,math.ceil(remaining*1000)))
            return
        mode=self._pending
        # Clear before the callback, so reentrant requests start a fresh period.
        self.cancel()
        self.callback(mode)
