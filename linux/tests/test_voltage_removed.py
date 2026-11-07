"""Retired voltage slots must never remain selectable or request sensors."""
import os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from metrics_overlay import HardwareOverlay,CPU_CHOICES,GPU_CHOICES
from cpu_telemetry import CpuTelemetry
from hardware import Hardware
from telemetry_demand import demand

class VoltageRemovalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_legacy_voltage_retires_only_its_side_of_slot(self):
  with tempfile.TemporaryDirectory() as folder:
   settings=QSettings(str(Path(folder)/'settings'),QSettings.IniFormat)
   settings.setValue('overlay_col_1','Voltage|Power')
   settings.setValue('overlay_col_2','Usage|Voltage')
   hud=HardwareOverlay(settings)
   self.assertEqual(hud.columns[0],('None','Power'))
   self.assertEqual(hud.columns[1],('Usage','None'))
   self.assertEqual(settings.value('overlay_col_1'),'None|Power')
   self.assertEqual(settings.value('overlay_col_2'),'Usage|None')
   hud.close()
 def test_voltage_is_not_a_sensor_or_metric(self):
  self.assertNotIn('Voltage',CPU_CHOICES);self.assertNotIn('Voltage',GPU_CHOICES)
  self.assertFalse(hasattr(CpuTelemetry,'voltage'));self.assertFalse(hasattr(Hardware,'gpu_voltage'))
  self.assertEqual(demand({'visible':True,'cpu':['Voltage'],'gpu':['Voltage']}),(set(),set()))
  with tempfile.TemporaryDirectory() as folder:
   self.assertFalse(any('voltage' in key for key in CpuTelemetry(Path(folder)).snapshot(set())))
