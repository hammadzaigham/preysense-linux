"""Honest telemetry and transparent rendering of the compact overlay."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from metrics_overlay import HardwareOverlay, numeric, metric_text, DEFAULT_COLUMNS, column_text

class OverlayPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
    def test_formatting_zero_units_and_invalid(self):
        self.assertEqual(metric_text(0, '%'), '0%')
        self.assertEqual(metric_text('0W', 'W', 1), '0.0W')
        for value in (None, True, float('nan'), float('inf'), -1, 'Sleeping'):
            self.assertEqual(metric_text(value), '—')
        self.assertEqual(metric_text(0, '°C', positive=True), '—')
        self.assertEqual(numeric('23.5%'), 23.5)
    def test_windows_paired_column_defaults_persistence_and_missing_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory)/'prefs'), QSettings.IniFormat)
            h = HardwareOverlay(settings)
            self.assertEqual(tuple(h.columns), DEFAULT_COLUMNS)
            self.assertEqual(h.column_graphs, [False, False, False, False, True, False, False])
            original_width = h._measure_layout(2)['width']
            self.assertTrue(h.add_slot('Fan Speed', 'None', True))
            self.assertGreater(h._measure_layout(2)['width'], original_width)
            restored = HardwareOverlay(settings)
            self.assertEqual(restored.columns[-1], ('Fan Speed', 'None'))
            self.assertTrue(restored.column_graphs[-1])
            self.assertEqual(column_text({'cpu_p_core_mhz': 4500}, 'Effective Clock'), '4500MHz')
            self.assertEqual(column_text({'memory': 55}, 'Memory'), 'N/A')
            self.assertEqual(column_text({'cpu_fan': 0}, 'Fan Speed'), '0RPM')
            restored.close(); h.close()

    def test_populated_graph_render_and_text_opacity(self):
        with tempfile.TemporaryDirectory() as directory:
            h = HardwareOverlay(QSettings(str(Path(directory)/'prefs'), QSettings.IniFormat))
            while h.columns:
                h.remove_slot(0)
            h.add_slot('Usage', 'Usage', True)
            h.show()
            for i in range(60):
                h.update_data({'cpu_usage': i, 'gpu': {'usage': 100-i}})
            image = h.grab().toImage()
            # Inspect the graph region, not the colored CPU/GPU row labels.
            pixels = [image.pixelColor(x,y) for x in range(image.width()-125, image.width()-10)
                      for y in range(8, image.height()-8)]
            self.assertTrue(any(c.blue() > c.red()+35 and c.green() > c.red()+35 for c in pixels))
            self.assertTrue(any(c.green() > c.red()+35 and c.green() > c.blue()+10 for c in pixels))
            h.configure('alpha', 0)
            faded = h.grab().toImage()
            c = faded.pixelColor(faded.width()-60, 15)
            self.assertLess(abs(c.red()-c.blue()), 5)
            h.close()

    def test_graph_zero_is_valid_missing_is_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            h = HardwareOverlay(QSettings(str(Path(directory)/'prefs'), QSettings.IniFormat))
            h.show()
            h.update_data({'cpu_usage': 0, 'gpu': {'usage': '0%'}})
            self.assertTrue(h.cpu_history_valid[-1])
            self.assertTrue(h.gpu_history_valid[-1])
            h.update_data({'cpu_usage': float('nan'), 'gpu': {'usage': 101}})
            self.assertFalse(h.cpu_history_valid[-1])
            self.assertFalse(h.gpu_history_valid[-1])
            h.configure('background', 0); h.configure('alpha', 0)
            image = h.grab().toImage()
            self.assertTrue(all(image.pixelColor(x,y).alpha() == 0 for x,y in ((0,0),(20,20),(image.width()-1,image.height()-1))))
            h.close()

if __name__ == '__main__': unittest.main()
