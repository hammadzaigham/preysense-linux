import json, os, sys, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibration import Calibrator

try:
    import PySide6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False


class StartupCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'calibration.json'
        dmi = self.root / 'class/dmi/id'
        dmi.mkdir(parents=True)
        for name, value in (('sys_vendor', 'Acer'), ('product_name', 'Test model'), ('bios_version', '1.0')):
            (dmi / name).write_text(value)
        self.data = {
            'model': 'Test model', 'profile': '1', 'fan_mode': '1 1',
            'cpu_power': {'domains': {'intel-rapl-mmio:0': {'pl1': 65., 'pl2': 140., 'tau': 55.967744}}},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_profiles_require_capture(self):
        calibrator = Calibrator(self.path, self.root)
        self.assertFalse(calibrator.has_profile())
        calibrator.update(self.data)
        self.assertTrue(Calibrator(self.path, self.root).has_profile())

    def test_corrupt_or_empty_profile_requires_capture(self):
        self.path.write_text('bad JSON')
        self.assertFalse(Calibrator(self.path, self.root).has_profile())
        self.path.unlink()
        calibrator = Calibrator(self.path, self.root)
        calibrator.update({'model': 'Test model', 'profile': '255'})
        self.assertFalse(calibrator.has_profile())

    def test_mmio_limits_saved_and_missing_values_fill(self):
        calibrator = Calibrator(self.path, self.root)
        calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Balanced']['pl1'], 65.)
        self.assertEqual(calibrator.cache['Balanced']['pl2'], 140.)
        self.data['cpu_power']['domains']['intel-rapl-mmio:0'] = {'pl1': 85., 'pl2': 140., 'tau': 55.967744}
        calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Balanced']['pl1'], 65.)
        self.data['profile'] = '5'
        calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Turbo']['pl1'], 85.)

    def test_missing_or_nonfinite_driver_values_are_not_guessed(self):
        self.data['cpu_power']['domains']['intel-rapl-mmio:0'] = {'pl1': float('nan'), 'pl2': 0, 'tau': 55.967744}
        calibrator = Calibrator(self.path, self.root)
        calibrator.update(self.data)
        self.assertNotIn('Balanced', calibrator.cache)

    @unittest.skipUnless(HAS_QT, 'PySide6 required')
    def test_worker_starts_cycle_on_queued_calibration_command(self):
        from preysense import Worker
        worker = Mock()
        worker.calibration_enabled = False
        Worker.command(worker, 'calibrate', True)
        worker.begin_calibration.assert_called_once()
        worker.hardware.write.assert_not_called()
        worker.poll.assert_not_called()

    @unittest.skipUnless(HAS_QT, 'PySide6 required')
    def test_startup_runs_automatic_capture_without_consent(self):
        from preysense import Window
        owner = Mock()
        owner._calibration_needed = True
        owner.quitting = False
        with patch('calibration_ui.run_calibration', return_value=True) as run:
            Window.prompt_startup_calibration(owner)
        run.assert_called_once_with(owner)
        self.assertFalse(owner._calibration_needed)

    @unittest.skipUnless(HAS_QT, 'PySide6 required')
    def test_confirm_calibration_is_noop_accept(self):
        from calibration_ui import confirm_calibration
        self.assertTrue(confirm_calibration(None))


if __name__ == '__main__':
    unittest.main()
