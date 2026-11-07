"""Actual Qt hide/close state must clear all overlay-only sensor demand."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QWidget
from metrics_overlay import HardwareOverlay
from telemetry_demand import demand

class OverlayVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.hud=HardwareOverlay(QSettings(str(Path(self.tmp.name)/'prefs'),QSettings.IniFormat))
        self.events=[];self.hud.metrics_changed.connect(self.events.append)
    def tearDown(self):self.hud.close();self.tmp.cleanup()
    def test_show_hide_and_reshow_publish_only_actual_visible_demand(self):
        self.assertEqual(self.hud.requested_metrics(),{'cpu':[],'gpu':[],'visible':False})
        self.hud.show();self.app.processEvents()
        self.assertTrue(self.events[-1]['visible']);self.assertTrue(self.events[-1]['cpu'])
        QWidget.hide(self.hud);self.app.processEvents()
        self.assertEqual(self.events[-1],{'cpu':[],'gpu':[],'visible':False})
        self.hud.show();self.app.processEvents();self.assertTrue(self.events[-1]['visible'])
    def test_close_clears_demand_and_hidden_slot_edits_stay_empty(self):
        self.hud.show();self.app.processEvents();self.hud.close();self.app.processEvents()
        self.assertEqual(self.events[-1],{'cpu':[],'gpu':[],'visible':False})
        self.hud.set_column(0,'Usage','Power',True)
        self.assertEqual(self.hud.requested_metrics(),{'cpu':[],'gpu':[],'visible':False})
    def test_minimized_overlay_stops_demand_until_restored(self):
        self.hud.show();self.app.processEvents()
        self.hud.showMinimized();self.app.processEvents()
        self.assertEqual(self.events[-1],{'cpu':[],'gpu':[],'visible':False})
        self.hud.showNormal();self.app.processEvents();self.assertTrue(self.events[-1]['visible'])

    def test_hidden_updates_do_not_collect_any_history_or_geometry(self):
        before={key:list(history) for key,history in self.hud.metric_history.items()}
        usage=list(self.hud.cpu_usage_history)
        with patch.object(self.hud,'_ensure_geometry') as geometry,patch.object(self.hud,'update') as repaint:
            self.hud.update_data({'cpu_usage':50,'gpu':{'usage':60}})
        self.assertEqual({key:list(history) for key,history in self.hud.metric_history.items()},before)
        self.assertEqual(list(self.hud.cpu_usage_history),usage)
        geometry.assert_not_called();repaint.assert_not_called()
    def test_hidden_overlay_leaves_only_independent_fan_temperature_demand(self):
        request=self.hud.requested_metrics()
        self.assertEqual(demand(request),(set(),set()))
        self.assertEqual(demand(request,True),({'cpu_temp'},{'temperature'}))
