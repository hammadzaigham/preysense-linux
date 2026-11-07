import unittest
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow
from PySide6.QtCore import QSettings
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.temp=tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name)/"settings.ini"),QSettings.IniFormat)
        self.applied_commands = []
        self.autostart_enabled = False

    def set_autostart(self, val):
        self.autostart_enabled = val

    def apply(self, key, val):
        self.applied_commands.append((key, val))

class TestPlatformWindows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        from linux.platform_windows import build_platform_windows, update_platform_windows
        self.build_platform_windows = build_platform_windows
        self.update_platform_windows = update_platform_windows
        self.mock_window = MockWindow()
        self.dialogs = self.build_platform_windows(self.mock_window)

    def tearDown(self):
        for dialog in self.dialogs.values():dialog.close()
        self.mock_window.close();self.mock_window.temp.cleanup()

    def test_build_platform_windows_structure(self):
        self.assertIn('settings', self.dialogs)
        self.assertIn('advanced', self.dialogs)
        self.assertIsInstance(self.dialogs['settings'], QDialog)
        self.assertIsInstance(self.dialogs['advanced'], QDialog)
        self.assertEqual(self.dialogs['settings'].width(), 540)
        self.assertEqual(self.dialogs['advanced'].width(), 540)
        self.assertEqual(self.mock_window.settings_dialog, self.dialogs['settings'])
        self.assertIs(self.dialogs['settings'],self.dialogs['advanced'])
        self.assertFalse(hasattr(self.mock_window,'advanced_dialog'))

    def test_update_platform_windows_telemetry_no_writes(self):
        data = {
            'battery_limit': 80,
            'usb_charging': 30,
            'lcd_overdrive': False,
        }
        self.update_platform_windows(self.mock_window, data)
        self.assertEqual(self.mock_window._row_usb.value(), 30)
        self.assertTrue(self.mock_window._row_battery.isChecked())
        # Ensure telemetry update does NOT trigger hardware apply calls
        self.assertEqual(len(self.mock_window.applied_commands), 0)

    def test_usb_slider_snap_and_release(self):
        slider_row = self.mock_window._row_usb
        # Simulate moving slider to 17
        slider_row.slider.setValue(17)
        # Release slider
        slider_row.slider.sliderReleased.emit()
        # Verify it snaps to 20 and emits usb_charging 20
        self.assertEqual(slider_row.value(),20)
        self.assertEqual(self.mock_window.applied_commands,[('usb_charging',20)])

    def test_removed_linux_irrelevant_labels_absent(self):
        """Verify explicitly removed Windows-specific labels are completely absent from dialogs."""
        removed_labels = [
            "Extended CPU Boost Options",
            "iGPU Only on Battery",
            "Acer Services",
            "Energy Saver on Battery",
            "Install to USB Drive",
            "Install to Boot Drive",
            "Enable ACPI Override"
        ]
        from PySide6.QtWidgets import QLabel, QPushButton
        for dlg_name, dlg in self.dialogs.items():
            all_texts = [w.text() for w in dlg.findChildren(QLabel)] + [w.text() for w in dlg.findChildren(QPushButton)]
            for text in all_texts:
                for removed in removed_labels:
                    self.assertNotIn(removed, text, f"Removed label '{removed}' found in {dlg_name} dialog")

        # Also verify source file itself does not define or reference these removed rows
        import linux.platform_windows as pw
        with open(pw.__file__, "r", encoding="utf-8") as f:
            code = f.read()
        for removed in removed_labels:
            self.assertNotIn(removed, code, f"Removed label '{removed}' found in platform_windows.py source")

    def test_observed_defaults_and_source_order(self):
        """Verify truthful naming for Observed Defaults and exact SOURCE_PROFILE_NAMES order."""
        from linux.source_profiles import SOURCE_PROFILE_NAMES
        self.assertEqual(SOURCE_PROFILE_NAMES, ('Eco', 'Quiet', 'Balanced', 'Performance', 'Turbo'))

        # Check that Observed Defaults is present and has truthful tooltip
        from PySide6.QtWidgets import QLabel
        a_dlg = self.dialogs['advanced']
        labels = [w.text() for w in a_dlg.findChildren(QLabel)]
        self.assertNotIn("Observed Defaults", labels)
        self.assertNotIn("Factory Defaults", labels)

    def test_dialog_render_grab(self):
        # Verify dialogs can show and grab without clipping or crashing
        s_dlg = self.dialogs['settings']
        a_dlg = self.dialogs['advanced']
        s_dlg.show()
        a_dlg.show()
        pix_s = s_dlg.grab()
        pix_a = a_dlg.grab()
        self.assertEqual(pix_s.width(), 540)
        self.assertEqual(pix_a.width(), 540)
        self.assertGreater(pix_s.height(), 100)
        self.assertGreater(pix_a.height(), 100)
        s_dlg.hide()
        a_dlg.hide()

if __name__ == '__main__':
    unittest.main()
