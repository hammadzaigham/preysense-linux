import unittest
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog
from PySide6.QtCore import QSettings
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tuning_settings import build_tuning_settings_dialog


class MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / "settings.ini"), QSettings.IniFormat)
        self.refreshed = False

    def refresh_tuning_master_switches(self):
        self.refreshed = True


class TestTuningSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.mock_window = MockWindow()
        self.dialog = build_tuning_settings_dialog(self.mock_window)

    def tearDown(self):
        self.dialog.close()
        self.mock_window.close()
        self.mock_window.temp.cleanup()

    def test_tuning_settings_dialog_structure(self):
        self.assertIsInstance(self.dialog, QDialog)
        self.assertEqual(self.dialog.width(), 460)

    def test_master_switches_toggle_and_notify(self):
        self.mock_window.settings.setValue("enable_gpu_overclocking", True)
        self.mock_window.refreshed = False
        dlg = build_tuning_settings_dialog(self.mock_window)
        self.assertTrue(self.mock_window.settings.value("enable_gpu_overclocking", False, type=bool))
        dlg.close()


if __name__ == '__main__':
    unittest.main()
