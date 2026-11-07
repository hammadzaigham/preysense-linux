"""Test PreySense Metrics Overlay controls and settings dialog."""
import os, sys, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, Signal, Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QCheckBox, QDialog
from metrics_overlay import HardwareOverlay, MetricsOverlay, controls

class Owner(QWidget):
    feedback = Signal(str, bool)
    def __init__(self, overlay, settings):
        super().__init__()
        self.overlay = overlay
        self.settings = settings
        self.overlay_toggle = QCheckBox()
        self.overlay_toggle.setChecked(False)

class OverlaySlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / 'settings.ini'), QSettings.IniFormat)
        self.hud = HardwareOverlay(self.settings)

    def tearDown(self):
        self.hud.close()
        self.temp.cleanup()

    def test_overlay_and_settings_use_utility_no_focus_flags(self):
        flags=self.hud.windowFlags()
        self.assertTrue(flags & Qt.WindowStaysOnTopHint)
        self.assertTrue(flags & Qt.WindowDoesNotAcceptFocus)
        self.assertEqual(flags & Qt.WindowType_Mask,Qt.Tool)
        owner=Owner(self.hud,self.settings)
        dialog=QDialog(owner);layout=QVBoxLayout(dialog)
        controls(owner,layout)
        self.assertEqual(dialog.windowFlags() & Qt.WindowType_Mask,Qt.Tool)
        self.assertTrue(dialog.windowFlags() & Qt.FramelessWindowHint)
        self.assertEqual(dialog.width(),540)
        from window_chrome import WindowTitleBar
        self.assertEqual(len(dialog.findChildren(WindowTitleBar)),1)
        self.assertEqual(dialog.findChild(WindowTitleBar).height(),30)
        dialog.close();owner.close()

    def test_controls_building(self):
        owner = Owner(self.hud, self.settings)
        layout = QVBoxLayout(owner)
        controls(owner, layout)
        self.assertTrue(layout.count() >= 5)
        owner.close()

if __name__ == '__main__':
    unittest.main()
