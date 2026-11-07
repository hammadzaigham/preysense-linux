import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from preysense import Worker
from fan_curve import FanCurve, DEFAULT_DUTIES

class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QCoreApplication.instance() or QCoreApplication([])
    def setUp(self):
        self.w=Worker(); self.w.hardware=Mock(); self.w.hardware.root=Path("/nonexistent"); self.w.curve=FanCurve(DEFAULT_DUTIES,DEFAULT_DUTIES)
        self.w.calibrator=Mock()
        self.w.system_power=Mock();self.w.system_power.sync.return_value={};self.w.system_power.shutdown.return_value={}
        self.w.hardware.snapshot.return_value={'cpu_temp':'60','gpu_temp':'55'}
        self.w.hardware.gpu_snapshot.return_value={'temperature':'55'}
    def test_curve_uses_hotter_sensor(self):
        self.w.hardware.snapshot.return_value={'cpu_temp':'60','gpu_temp':'80'}
        self.w.hardware.gpu_snapshot.return_value={'temperature':'80'}
        self.w.poll()
        expected_duty = FanCurve(DEFAULT_DUTIES,DEFAULT_DUTIES).target(80)
        self.w.hardware.fan_duty.assert_called_once_with(*expected_duty)
        self.w.hardware.gpu_snapshot.assert_called_once_with(requested={'temperature'})
    def test_missing_cpu_restores_automatic(self):
        self.w.hardware.snapshot.return_value={'cpu_temp':None,'gpu_temp':'55'}
        self.w.poll()
        self.assertIsNone(self.w.curve)
        self.w.hardware.write.assert_called_once_with('fan_mode',0)
        self.w.hardware.fan_duty.assert_not_called()
    def test_manual_write_failure_restores_automatic(self):
        self.w.hardware.fan_duty.side_effect=OSError('gone')
        self.w.poll()
        self.assertIsNone(self.w.curve)
        self.w.hardware.write.assert_called_once_with('fan_mode',0)
    def test_saved_fan_policy_follows_mode_changes(self):
        self.w.curve=None
        self.w.fan_policies={'0':{'kind':'Max'},'1':{'kind':'Auto'}}
        self.w.hardware.snapshot.return_value={'profile':'0','cpu_temp':'60','gpu_temp':'55'}
        self.w.poll()
        self.w.hardware.write.assert_called_with('fan_mode',1)
        self.w.last_sensor_poll = float('-inf')
        self.w.cached_data = None
        self.w.hardware.snapshot.return_value={'profile':'1','cpu_temp':'60','gpu_temp':'55'}
        self.w.poll()
        self.w.hardware.write.assert_called_with('fan_mode',0)
    def test_editing_inactive_policy_does_not_change_hardware(self):
        self.w.curve=None
        self.w.hardware.bridge_read.return_value='1'
        self.w.hardware.snapshot.return_value={'profile':'1','cpu_temp':'60','gpu_temp':'55'}
        self.w.command('fan_policy',{'mode':0,'policy':{'kind':'Max'}})
        self.w.hardware.write.assert_not_called()
        self.assertEqual(self.w.fan_policies['0']['kind'],'Max')
    def test_explicit_mode_ends_curve_ownership(self):
        self.w.command('profile',1)
        self.assertIsNone(self.w.curve)
        self.w.hardware.write.assert_called_once_with('profile',1)
if __name__=='__main__': unittest.main()
