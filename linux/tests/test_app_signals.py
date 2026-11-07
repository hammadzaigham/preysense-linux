import os,signal,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication,QTimer
from app_signals import SignalWakeup
class SignalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])
 def test_signal_wakes_idle_loop_without_recurring_timer(self):
  wake=SignalWakeup();old=signal.getsignal(signal.SIGUSR1);seen=[]
  signal.signal(signal.SIGUSR1,lambda *_:(seen.append(True),self.app.quit()))
  QTimer.singleShot(0,lambda:os.kill(os.getpid(),signal.SIGUSR1))
  timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(self.app.quit);timer.start(1000)
  try:self.app.exec();self.assertEqual(seen,[True])
  finally:timer.stop();signal.signal(signal.SIGUSR1,old);wake.close()
