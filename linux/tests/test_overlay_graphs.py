"""Windows graph history and area-rendering behavior."""
import os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from metrics_overlay import HardwareOverlay,graph_value,column_text,CPU_GRAPH_COLOR

class WindowsGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.hud=HardwareOverlay(QSettings(str(Path(self.temp.name)/'prefs'),QSettings.IniFormat))
        for i in range(8):self.hud.set_column(i,'None','None',False)
    def tearDown(self):self.hud.close();self.temp.cleanup()
    def test_missing_is_zero_and_memory_uses_windows_mb_units(self):
        self.assertEqual(graph_value({},'Power'),0)
        self.assertEqual(graph_value({'memory_used_gb':2},'Memory'),2048)
        self.assertEqual(graph_value({'gpu':{'memory_used_gb':3}},'Memory',True),3072)
    def test_ram_and_gpu_memory_display_requested_mhz_label(self):
        self.assertEqual(column_text({'memory_speed_mhz':6400},'Memory Speed'),'6400MHz')
        self.assertEqual(column_text({'gpu':{'memory_clock_mhz':9000}},'Memory Speed',True),'9000MHz')
    def test_only_enabled_visible_metrics_collect_and_history_is_sixty_samples(self):
        self.hud.set_column(0,'Usage','Power',True)
        self.hud.update_data({'cpu_usage':23})
        self.assertEqual(list(self.hud.metric_history[(False,'Usage')]),[0]*60)
        self.hud.show()
        for i in range(65):self.hud.update_data({'cpu_usage':i})
        self.assertEqual(set(self.hud.metric_history),{(False,'Usage'),(True,'Power')})
        self.assertEqual(list(self.hud.metric_history[(False,'Usage')]),list(range(5,65)))
        self.assertEqual(self.hud.metric_history[(True,'Power')][-1],0)
    def test_disabling_then_reenabling_clears_but_shared_metric_retains_history(self):
        self.hud.set_column(0,'Usage','None',True);self.hud.show()
        self.hud.update_data({'cpu_usage':77})
        self.hud.set_column(1,'Usage','None',True)
        self.hud.set_column(0,'None','None',False)
        self.assertEqual(self.hud.metric_history[(False,'Usage')][-1],77)
        self.hud.set_column(1,'Usage','None',False)
        self.hud.set_column(1,'Usage','None',True)
        self.assertEqual(list(self.hud.metric_history[(False,'Usage')]),[0]*60)
    def test_renderer_fills_under_curve_without_glow(self):
        image=QImage(100,50,QImage.Format_ARGB32_Premultiplied);image.fill(0)
        p=QPainter(image)
        self.hud.draw_mini_graph(p,0,0,99,49,[50]*60,CPU_GRAPH_COLOR,fill_alpha=24)
        p.end()
        self.assertEqual(image.pixelColor(50,40).alpha(),24)
        self.assertEqual(image.pixelColor(50,10).alpha(),0)
