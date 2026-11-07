"""Wake an idle Qt event loop for Python signals without a polling timer."""
import os,signal
from PySide6.QtCore import QObject,QSocketNotifier

class SignalWakeup(QObject):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.reader,self.writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        self.previous=signal.set_wakeup_fd(self.writer)
        self.notifier=QSocketNotifier(self.reader,QSocketNotifier.Read,self)
        self.notifier.activated.connect(self.drain)
    def drain(self,*_):
        if self.reader is None:return
        try:
            while os.read(self.reader,4096):pass
        except (BlockingIOError,OSError):pass
    def close(self):
        if self.reader is None:return
        self.notifier.setEnabled(False);signal.set_wakeup_fd(self.previous)
        os.close(self.reader);os.close(self.writer);self.reader=self.writer=None
