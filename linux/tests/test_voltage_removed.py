"""GPU Voltage stays retired; CPU Voltage/VID is a first-class overlay metric."""
import os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from metrics_overlay import HardwareOverlay,CPU_CHOICES,GPU_CHOICES
from hardware import Hardware
from telemetry_demand import demand

class VoltagePolicyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_gpu_voltage_legacy_slot_retires(self):
  with tempfile.TemporaryDirectory() as folder:
   settings=QSettings(str(Path(folder)/'settings'),QSettings.IniFormat)
   settings.setValue('overlay_col_1','Usage|Voltage')
   hud=HardwareOverlay(settings)
   self.assertEqual(hud.columns[0],('Usage','None'))
   self.assertEqual(settings.value('overlay_col_1'),'Usage|None')
   hud.close()
 def test_cpu_voltage_is_kept_gpu_voltage_is_not_a_metric(self):
  self.assertIn('Voltage',CPU_CHOICES);self.assertNotIn('Voltage',GPU_CHOICES)
  self.assertFalse(hasattr(Hardware,'gpu_voltage'))
  self.assertEqual(demand({'visible':True,'cpu':['Voltage'],'gpu':['Voltage']}),({'cpu_voltage_v'},set()))
