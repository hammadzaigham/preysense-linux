"""Test PreySense native HardwareOverlay implementation."""
import os, sys, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from metrics_overlay import HardwareOverlay, MetricsOverlay

class OverlayTests(unittest.TestCase):
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

    def test_scale_opacity_configuration(self):
        self.hud.configure('scale', 150)
        self.hud.configure('background', 40)
        self.hud.configure('alpha', 80)
        self.assertEqual(self.hud.scale_percent, 150)
        self.assertEqual(self.hud.bg_alpha, 40)
        self.assertEqual(self.hud.text_alpha, 80)
        self.assertEqual(self.settings.value('hud_background'), 40)

    def test_missing_gpu_data_and_history_are_valid(self):
        self.hud.show()
        self.hud.update_data({'cpu_usage': 20, 'gpu': {'status': 'Sleeping'}})
        self.assertEqual(self.hud.cpu_usage_history[-1], 20)
        self.assertEqual(self.hud.gpu_usage_history[-1], 0.0)
        for i in range(100):
            self.hud.update_data({'cpu_usage': i})
        self.assertEqual(len(self.hud.cpu_usage_history), 60)

    def test_alias(self):
        self.assertIs(MetricsOverlay, HardwareOverlay)

if __name__ == '__main__':
    unittest.main()
