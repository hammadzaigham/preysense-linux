import os,sys,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QSlider
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from slider_snap import configure_snap
class SnapTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_drag_commits_only_grid_values(self):
  s=QSlider(Qt.Horizontal);s.setRange(0,100);s.resize(300,28);configure_snap(s,25);values=[];s.valueChanged.connect(values.append);released=[];s.sliderReleased.connect(lambda:released.append(True));s.show()
  QTest.mousePress(s,Qt.LeftButton,pos=QPoint(98,14));QTest.mouseMove(s,QPoint(203,14));QTest.mouseRelease(s,Qt.LeftButton,pos=QPoint(203,14))
  self.assertTrue(values);self.assertTrue(all(v in (0,25,50,75,100) for v in values));self.assertEqual(released,[True]);s.close()
 def test_bounds_and_keyboard_steps(self):
  s=QSlider(Qt.Horizontal);s.setRange(50,200);configure_snap(s,5);s.setValue(100);QTest.keyClick(s,Qt.Key_Right);self.assertEqual(s.value(),105);self.assertEqual(s._preysense_snap.snap(1000),200);s.close()

class SliderPaintTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def tearDown(self):
  self.app.setStyleSheet('')
 def test_handle_fits_widget_at_both_limits(self):
  import design
  from PySide6.QtWidgets import QStyle,QStyleOptionSlider
  self.app.setStyleSheet(design.STYLE)
  for value in (0,100):
   slider=QSlider(Qt.Horizontal);slider.setRange(0,100);slider.resize(220,24);slider.setValue(value);slider.show();self.app.processEvents()
   option=QStyleOptionSlider();slider.initStyleOption(option)
   handle=slider.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,slider)
   self.assertTrue(slider.rect().contains(handle),handle)
   slider.close()
