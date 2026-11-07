import os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QLocale
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QComboBox
from appearance import Appearance
class AppearanceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.owner=QWidget();self.owner.settings=QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.IniFormat)
  self.label=QLabel('Balanced',self.owner);self.combo=QComboBox(self.owner);self.combo.addItem('Quiet',0);self.ui=Appearance(self.owner)
 def tearDown(self):
  self.ui.set_language('en-US',False);self.ui.set_theme('Dark',False);self.app.setStyleSheet('');self.owner.close();self.temp.cleanup()
 def test_translation_preserves_backend_enum_and_roundtrips(self):
  self.ui.set_language('zh-CN',False)
  self.assertEqual(self.label.text(),'均衡')
  self.assertEqual(self.combo.currentText(),'Quiet');self.assertEqual(self.combo.currentData(),0)
  self.assertEqual(self.combo.itemDelegate().displayText('Quiet',QLocale()),'安静')
  self.ui.set_language('en-US',False);self.assertEqual(self.label.text(),'Balanced')
 def test_original_light_palette_and_preference(self):
  self.ui.set_theme('Light')
  self.assertIn('#F5F6F8',self.app.styleSheet());self.assertIn('#17191C',self.app.styleSheet())
  self.assertEqual(self.owner.settings.value('theme'),'Light')
if __name__=='__main__':unittest.main()
