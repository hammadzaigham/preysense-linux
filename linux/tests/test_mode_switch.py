"""Manual-mode debounce deadlines; no firmware or desktop writes."""
import os,sys,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, Qt
from mode_switch import ModeSwitch

class ModeSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])
    def setUp(self):
        self.now=10.0;self.calls=[]
        self.switch=ModeSwitch(self.calls.append,clock=lambda:self.now)
    def tearDown(self):self.switch.cancel()
    def test_full_second_and_early_wakeup(self):
        self.switch.request(5)
        self.assertEqual(self.switch.pending,5)
        self.assertEqual(self.switch.timer.timerType(),Qt.PreciseTimer)
        self.now=10.999;self.switch.flush()
        self.assertEqual(self.calls,[]);self.assertTrue(self.switch.timer.isActive())
        self.now=11;self.switch.flush();self.switch.flush()
        self.assertEqual(self.calls,[5]);self.assertIsNone(self.switch.pending)
    def test_latest_request_restarts_deadline(self):
        self.switch.request(0)
        self.now=10.8;self.switch.request(1)
        self.now=11.2;self.switch.request(4)
        self.now=12.199;self.switch.flush();self.assertFalse(self.calls)
        self.now=12.2;self.switch.flush();self.assertEqual(self.calls,[4])
    def test_same_request_also_restarts_quiet_period(self):
        self.switch.request(6)
        self.now=10.9;self.switch.request(6)
        self.now=11;self.switch.flush();self.assertFalse(self.calls)
        self.now=11.9;self.switch.flush();self.assertEqual(self.calls,[6])
        self.now=20;self.switch.request(6);self.now=21;self.switch.flush()
        self.assertEqual(self.calls,[6,6])
    def test_cancel_clears_timer_and_never_delivers(self):
        self.switch.request(0);self.switch.cancel();self.now=20;self.switch.flush()
        self.assertIsNone(self.switch.pending);self.assertFalse(self.switch.timer.isActive());self.assertFalse(self.calls)
    def test_invalid_modes_do_not_replace_valid_pending(self):
        self.switch.request(1)
        for mode in (True,False,2,3,-1,255,'5',5.0,None,{},[]):
            with self.assertRaises(ValueError):self.switch.request(mode)
        self.assertEqual(self.switch.pending,1)
    def test_reentrant_request_survives_callback(self):
        def callback(mode):self.calls.append(mode);self.switch.request(4)
        self.switch.callback=callback
        self.switch.request(1);self.now=11;self.switch.flush()
        self.assertEqual(self.calls,[1]);self.assertEqual(self.switch.pending,4)
    def test_invalid_clock_does_not_modify_request(self):
        for value in (True,float('nan'),float('inf'),None):
            self.now=value
            with self.assertRaises(ValueError):self.switch.request(5)
        self.assertIsNone(self.switch.pending)

if __name__=='__main__':unittest.main()
