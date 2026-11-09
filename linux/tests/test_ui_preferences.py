import os,sys,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QWidget,QComboBox,QDialog,QLabel,QSpinBox
from PySide6.QtCore import QSettings,QEvent,QCoreApplication,Qt
from appearance import Appearance,LANGUAGES
from tooltip_policy import install_no_tooltips
from platform_windows import build_platform_windows,update_platform_windows
from controls import FanGraph
class UiPreferencesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.owner=QWidget();self.owner.settings=QSettings(self.tmp.name+'/p',QSettings.IniFormat);self.owner.apply=lambda*a:None
 def tearDown(self):
  if hasattr(self.owner,'appearance'):self.owner.appearance.set_language('en-US',False);self.owner.appearance.set_theme('Dark',False)
  self.owner.close();self.tmp.cleanup()
 def test_language_names_do_not_translate(self):
  build_platform_windows(self.owner);self.owner.appearance=Appearance(self.owner)
  combo=self.owner._row_lang.combo
  for lang in LANGUAGES.values():
   self.owner.appearance.set_language(lang,False)
   self.assertEqual([combo.itemText(i) for i in range(combo.count())],list(LANGUAGES))
   from appearance import TranslationDelegate
   self.assertNotIsInstance(combo.itemDelegate(),TranslationDelegate)
 def test_usb_zero_is_off_for_edit_and_telemetry(self):
  build_platform_windows(self.owner);row=self.owner._row_usb
  self.assertEqual(row.label_value.text(),'Off')
  row.setValue(10);self.assertEqual(row.label_value.text(),'10%')
  update_platform_windows(self.owner,{'usb_charging':'0'});self.assertEqual(row.label_value.text(),'Off')
 def test_tooltip_changes_are_cleared(self):
  install_no_tooltips(self.app);widget=QWidget();widget.setToolTip('hidden');self.assertEqual(widget.toolTip(),'');widget.close()
 def test_fan_graph_left_edge_is_40_degrees(self):
  from fan_curve import GRAPH_MIN_C
  graph=FanGraph();graph.set_curve([GRAPH_MIN_C,50,60],[10,20,30],0)
  self.assertEqual(graph.point(0,50).x(),graph.plot().left())
  self.assertGreater(graph.point(1,50).x(),graph.plot().left());graph.close()
 def test_light_pressed_thumb_keeps_color(self):
  self.owner.appearance=Appearance(self.owner);self.owner.appearance.set_theme('Light',False)
  self.assertIn('background:#8B97AF',self.app.styleSheet())
