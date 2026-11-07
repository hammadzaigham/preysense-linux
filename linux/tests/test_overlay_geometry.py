"""Measured text boxes and logical-coordinate screen bounds for the native HUD."""
import os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QRect
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QApplication
from metrics_overlay import HardwareOverlay,column_text

class OverlayGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.hud=HardwareOverlay(QSettings(str(Path(self.tmp.name)/'prefs'),QSettings.IniFormat))
    def tearDown(self):self.hud.close();self.tmp.cleanup()
    def test_measured_values_fit_at_all_requested_scales(self):
        data={'cpu_p_core_mhz':6500,'cpu_e_core_mhz':4800,'cpu_fan':10000,'memory_used_gb':128.5,
              'gpu':{'clock':9500,'memory_used_gb':128.5,'memory_clock_mhz':15000},'gpu_fan':10000}
        self.hud.update_data(data)
        for scale in (50,75,100,125,150,200):
            self.hud.configure('scale',scale)
            layout=self.hud._layout;fm=QFontMetricsF(layout['font'])
            for i,pair in enumerate(self.hud.columns):
                for row,metric in enumerate(pair):
                    if metric!='None':self.assertGreaterEqual(layout['columns'][i][0],fm.horizontalAdvance(column_text(data,metric,bool(row))))
            last_bottom=layout['pad']+layout['inset']+2*layout['line']+layout['gap']
            self.assertLessEqual(last_bottom,self.hud.height()-layout['pad'])
            self.assertLessEqual(self.hud.width(),self.hud.get_current_screen().availableGeometry().width()-24)
    def test_all_anchors_fit_negative_origin_secondary_screen(self):
        geo=QRect(-1920,-200,1920,1040)
        screen=SimpleNamespace(availableGeometry=lambda:geo)
        with patch.object(self.hud,'get_current_screen',return_value=screen):
            self.hud.configure('scale',200)
            for h in ('Left','Center','Right'):
                for v in ('Top','Center','Bottom'):
                    self.hud.configure('h_pos',h);self.hud.configure('v_pos',v)
                    self.assertTrue(geo.contains(self.hud.geometry()),(h,v,self.hud.geometry()))
            self.assertEqual(self.hud.x(),geo.x()+geo.width()-self.hud.width()-12)
            self.assertEqual(self.hud.y(),geo.y()+geo.height()-self.hud.height()-12)
    def test_many_graphs_fit_screen_without_changing_requested_zoom(self):
        for i in range(8):self.hud.set_column(i,'Fan Speed','Memory Speed',True)
        self.hud.configure('scale',200)
        self.assertEqual(self.hud.scale_percent,200)
        self.assertLess(self.hud._layout['scale'],4)
        self.assertLessEqual(self.hud.width(),self.hud.get_current_screen().availableGeometry().width()-24)

if __name__=='__main__':unittest.main()


class OverlayOwnershipTests(unittest.TestCase):
    def test_overlay_is_owned_and_closes_with_application(self):
        from PySide6.QtWidgets import QApplication,QWidget
        from PySide6.QtCore import QSettings
        app=QApplication.instance() or QApplication([])
        owner=QWidget()
        with tempfile.TemporaryDirectory() as directory:
            hud=HardwareOverlay(QSettings(str(Path(directory)/'prefs'),QSettings.IniFormat),owner)
            self.assertIs(hud.parentWidget(),owner)
            hud.show();app.processEvents();app.aboutToQuit.emit()
            self.assertFalse(hud.isVisible())
            owner.close()

class OverlayGeometryCachingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.hud=HardwareOverlay(QSettings(str(Path(self.tmp.name)/'prefs'),QSettings.IniFormat))
    def tearDown(self):self.hud.close();self.tmp.cleanup()
    def test_hidden_samples_do_no_geometry_work(self):
        with patch.object(self.hud,'_measure_layout',wraps=self.hud._measure_layout) as measure,patch.object(self.hud,'reposition',wraps=self.hud.reposition) as position:
            for value in range(20):self.hud.update_data({'cpu_usage':value})
            measure.assert_not_called();position.assert_not_called()
    def test_visible_normal_values_do_not_recalculate_or_reposition(self):
        self.hud.show();self.app.processEvents()
        with patch.object(self.hud,'_measure_layout',wraps=self.hud._measure_layout) as measure,patch.object(self.hud,'reposition',wraps=self.hud.reposition) as position:
            for value in range(20):self.hud.update_data({'cpu_usage':value,'gpu':{'usage':100-value}})
            measure.assert_not_called();position.assert_not_called()
    def test_long_value_grows_once_and_cached_repeat_is_free(self):
        self.hud.show();self.app.processEvents()
        data={'gpu':{'clock':123456789}}
        with patch.object(self.hud,'recalculate_size',wraps=self.hud.recalculate_size) as resize:
            self.hud.update_data(data);self.assertEqual(resize.call_count,1)
            self.hud.update_data(data);self.assertEqual(resize.call_count,1)
        fm=QFontMetricsF(self.hud._layout['font'])
        self.assertGreaterEqual(self.hud._layout['columns'][2][0],fm.horizontalAdvance(column_text(data,'Clock',True)))
    def test_new_screen_geometry_invalidates_cached_size(self):
        self.hud.show();self.app.processEvents()
        geo=QRect(0,0,640,480);screen=SimpleNamespace(availableGeometry=lambda:geo)
        with patch.object(self.hud,'get_current_screen',return_value=screen),patch.object(self.hud,'recalculate_size',wraps=self.hud.recalculate_size) as resize:
            self.hud.update_data({});self.assertEqual(resize.call_count,1)
            self.hud.update_data({});self.assertEqual(resize.call_count,1)
            self.assertLessEqual(self.hud.width(),geo.width()-24)
