"""Styling contract and preserved native helper/documentation actions."""
import os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Signal,QSettings,Qt
from PySide6.QtWidgets import QApplication,QMainWindow,QDialog,QLabel,QPushButton
from platform_windows import build_platform_windows
from documentation_ui import DocumentationWindow
from window_chrome import WindowTitleBar

class Owner(QMainWindow):
    feedback=Signal(str,bool)
    def __init__(self,path):
        super().__init__();self.settings=QSettings(str(path),QSettings.IniFormat);self.calls=[]
    def apply(self,*args):self.calls.append(args)
    def set_autostart(self,value):pass

class PlatformChromeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.owner=Owner(Path(self.temp.name)/'prefs')
    def tearDown(self):self.owner.close();self.temp.cleanup()
    def test_settings_original_chrome_margins_and_compact_content(self):
        dialogs=build_platform_windows(self.owner)
        for name,dialog in dialogs.items():
            dialog.show();self.app.processEvents()
            bar=dialog.findChild(WindowTitleBar)
            self.assertIsNotNone(bar);self.assertEqual(bar.height(),30)
            self.assertEqual(bar.close_button.size().toTuple(),(30,30))
            self.assertEqual(dialog.width(),540)
            self.assertEqual(dialog.layout().contentsMargins().left(),0)
            margin=dialog._platform_content.layout().contentsMargins()
            self.assertEqual((margin.left(),margin.top(),margin.right(),margin.bottom()),(14,10,14,8))
            self.assertLess(dialog.height(),600)
            self.assertIs(dialog.property('preysenseShell'),True)
            dialog.close()
    def test_switch_sizes_and_remaining_settings_order(self):
        dialogs=build_platform_windows(self.owner)
        labels=[w.text() for w in dialogs['settings'].findChildren(QLabel)]
        expected=['Run on Startup','Language','Theme','Battery Limit','USB Power-Off Charging']
        self.assertEqual([label for label in labels if label in expected],expected)
        self.assertEqual(self.owner._row_startup.switch.size().toTuple(),(56,28))
        self.assertEqual(self.owner._row_theme.switch.size().toTuple(),(92,28))
        self.assertEqual(self.owner._row_battery.switch.size().toTuple(),(92,28))
    def test_documentation_navigation_and_header_close_remain(self):
        dialog=DocumentationWindow(self.owner)
        self.assertEqual(dialog.findChild(WindowTitleBar).height(),30)
        self.assertIn('PreySense for Linux documentation',dialog.browser.toPlainText())
        self.assertTrue(any(button.text()=='Back' and button.height()==28 for button in dialog.findChildren(QPushButton)))
        dialog.load(dialog.root/'docs/linux/telemetry.md');self.assertEqual(len(dialog.history),2)
        dialog.back();self.assertEqual(len(dialog.history),1)
        dialog.close()
