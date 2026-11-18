import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gpu_clock_tuning import GpuClockTuning, GpuClockRange, GpuClockOffsets


class TestGpuClockTuning(unittest.TestCase):
    def test_range_contains_and_snap(self):
        core_range = GpuClockRange(0, 500, 5)
        self.assertTrue(core_range.contains(0))
        self.assertTrue(core_range.contains(250))
        self.assertTrue(core_range.contains(500))
        self.assertFalse(core_range.contains(-5))
        self.assertFalse(core_range.contains(505))

        self.assertEqual(core_range.snap(12), 10)
        self.assertEqual(core_range.snap(13), 15)
        self.assertEqual(core_range.snap(-10), 0)
        self.assertEqual(core_range.snap(600), 500)

        mem_range = GpuClockRange(0, 2000, 100)
        self.assertEqual(mem_range.snap(149), 100)
        self.assertEqual(mem_range.snap(151), 200)
        self.assertEqual(mem_range.snap(2500), 2000)

    def test_is_available_nvml(self):
        mock_nvml = MagicMock()
        mock_nvml.available = True
        mock_nvml.dev = 1
        tuning = GpuClockTuning(nvml=mock_nvml)
        self.assertTrue(tuning.is_available())

    def test_is_available_none(self):
        with patch('shutil.which', return_value=None):
            mock_nvml = MagicMock()
            mock_nvml.available = False
            mock_nvml.dev = None
            tuning = GpuClockTuning(nvml=mock_nvml)
            self.assertFalse(tuning.is_available())

    def test_apply_offsets_nvml_success(self):
        mock_nvml = MagicMock()
        mock_nvml.available = True
        mock_nvml.dev = 1
        mock_lib = MagicMock()
        mock_lib.nvmlDeviceSetGpcClkVfOffset.return_value = 0
        mock_lib.nvmlDeviceSetMemClkVfOffset.return_value = 0
        mock_nvml.lib = mock_lib

        tuning = GpuClockTuning(nvml=mock_nvml)
        ok, msg = tuning.apply_clock_offsets(100, 200)
        self.assertTrue(ok)
        self.assertEqual(msg, "GPU clock offsets applied.")
        mock_lib.nvmlDeviceSetGpcClkVfOffset.assert_called_once()
        mock_lib.nvmlDeviceSetMemClkVfOffset.assert_called_once()

    def test_apply_offsets_nvidia_settings_fallback(self):
        mock_nvml = MagicMock()
        mock_nvml.available = False
        with patch('shutil.which', return_value='/usr/bin/nvidia-settings'), \
             patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            tuning = GpuClockTuning(nvml=mock_nvml)
            ok, msg = tuning.apply_clock_offsets(100, 200)
            self.assertTrue(ok)
            self.assertEqual(msg, "GPU clock offsets applied.")
            mock_run.assert_called_once()

    def test_reset_clock_offsets(self):
        mock_nvml = MagicMock()
        mock_nvml.available = True
        mock_nvml.dev = 1
        mock_lib = MagicMock()
        mock_lib.nvmlDeviceSetGpcClkVfOffset.return_value = 0
        mock_lib.nvmlDeviceSetMemClkVfOffset.return_value = 0
        mock_nvml.lib = mock_lib

        tuning = GpuClockTuning(nvml=mock_nvml)
        ok, _ = tuning.reset_clock_offsets()
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
