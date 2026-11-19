import unittest
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QPushButton
from unittest.mock import patch
from PySide6.QtCore import QSettings
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tuning_settings import build_tuning_settings_dialog
from cpu_prochot import ProchotSnapshot
from ui_controls import SettingSwitchRow, SettingValueRow, RectangularSwitch


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
        switches = self.dialog.findChildren(SettingSwitchRow)
        self.assertEqual([row.label.text() for row in switches],
                         ['Enable CPU Power Limit Control', 'Enable GPU Power Limit Control'])
        self.assertTrue(all(row.isChecked() for row in switches))
        switches[0].setChecked(False)
        self.assertFalse(self.mock_window.settings.value('enable_cpu_power_limits', True, type=bool))
        self.assertTrue(self.mock_window.refreshed)

    @patch('cpu_prochot.CpuProchot.read', return_value=ProchotSnapshot(10, 100, False))
    def test_prochot_edits_require_save(self, _read):
        self.dialog.show()
        row = self.dialog.findChild(SettingValueRow)
        include = next(switch for switch in self.dialog.findChildren(RectangularSwitch)
                       if switch.accessibleName() == 'Include PROCHOT offset')
        include.setChecked(True)
        row.setValue(20)
        self.dialog.close()
        self.assertFalse(self.mock_window.settings.contains('prochot_offset'))

        self.dialog.show()
        self.assertEqual(row.value(), 10)
        include.setChecked(True)
        row.setValue(15)
        save = next(btn for btn in self.dialog.findChildren(QPushButton) if btn.text() == 'Save')
        save.click()
        self.assertEqual(self.mock_window.settings.value('prochot_offset', type=int), 15)
        self.assertTrue(self.mock_window.settings.value('apply_prochot', type=bool))


if __name__ == '__main__':
    unittest.main()
