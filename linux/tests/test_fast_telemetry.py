import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preysense import Worker
from metrics_overlay import HardwareOverlay
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

class FastTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['', '-platform', 'offscreen'])

    def test_overlay_requested_metrics_emits_demand(self):
        settings = QSettings()
        overlay = HardwareOverlay(settings)
        req = overlay.requested_metrics()
        self.assertIn("cpu", req)
        self.assertIn("gpu", req)
        self.assertIn("visible", req)

    def test_worker_respects_overlay_gpu_demand(self):
        w = Worker()
        w.hardware = Mock()
        w.hardware.root = Path("/nonexistent")
        del w.hardware._control_cache
        w.hardware.sensor_snapshot.return_value = {}
        w.hardware.snapshot.return_value = {'profile': '1', 'cpu_temp': '50', 'gpu_temp': '45'}
        w.system_power = Mock()
        w.system_power.sync.return_value = {}

        # 1. Overlay hidden: no GPU demand, gpu_snapshot not called
        w.overlay_demand = {"cpu": set(), "gpu": set(), "visible": False}
        w.poll()
        w.hardware.gpu_snapshot.assert_not_called()

        # 2. Overlay visible with Temperature and Usage only:
        w.overlay_demand = {"cpu": {"Usage"}, "gpu": {"Temperature", "Usage"}, "visible": True}
        w.last_sensor_poll = float('-inf')
        w.poll()
        w.hardware.gpu_snapshot.assert_called_with(requested={"temperature", "usage"})

    def test_single_shared_timer_stops_without_demand(self):
        from PySide6.QtCore import QTimer
        w = Worker()
        w.hardware = Mock()
        w.hardware.root = Path("/nonexistent")
        w.hardware.control_read.return_value = '1'
        w.hardware.snapshot.return_value = {'profile': '1'}
        w.hardware.sensor_snapshot.return_value = {}
        w.system_power = Mock(); w.system_power.sync.return_value = {}
        w.start()
        self.assertIsInstance(w.timer, QTimer)
        self.assertFalse(hasattr(w, 'fan_timer'))
        w.overlay_demand = {"cpu": set(), "gpu": set(), "visible": True}
        w.main_window_visible = False
        w.curve = None
        w.update_sampling_timer()
        self.assertFalse(w.timer.isActive())
        w.main_window_visible = True
        w.update_sampling_timer()
        self.assertTrue(w.timer.isActive())
        w.timer.stop()

if __name__ == '__main__':
    unittest.main()
