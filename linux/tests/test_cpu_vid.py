"""CPU VID (IA32_PERF_STATUS) decode and demand mapping — no Qt."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpu_telemetry import CpuTelemetry, MSR_IA32_PERF_STATUS
from telemetry_demand import demand


class CpuVidTests(unittest.TestCase):
    def test_decode_matches_windows(self):
        self.assertEqual(CpuTelemetry.decode_perf_status_vid(8192 << 32), 1.0)
        self.assertEqual(CpuTelemetry.decode_perf_status_vid(10240 << 32), 1.25)
        self.assertIsNone(CpuTelemetry.decode_perf_status_vid(0))
        self.assertIsNone(CpuTelemetry.decode_perf_status_vid((3 * 8192) << 32))

    def test_platform_sysfs_millivolts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'devices/platform/preysense/cpu_vid_mv'
            path.parent.mkdir(parents=True)
            path.write_text('1250\n')
            sensor = CpuTelemetry(root)
            self.assertEqual(sensor.core_voltage_vid(), 1.25)
            self.assertEqual(sensor.snapshot({'cpu_voltage_v'})['cpu_voltage_v'], 1.25)
            self.assertIsNone(sensor.snapshot(set())['cpu_voltage_v'])

    def test_msr_file_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'empty_sys').mkdir()
            msr = root / '0' / 'msr'
            msr.parent.mkdir(parents=True)
            blob = bytearray(MSR_IA32_PERF_STATUS + 8)
            raw = 8192 << 32
            blob[MSR_IA32_PERF_STATUS:MSR_IA32_PERF_STATUS + 8] = raw.to_bytes(8, 'little')
            msr.write_bytes(blob)
            sensor = CpuTelemetry(root / 'empty_sys', msrroot=root)
            self.assertEqual(sensor.core_voltage_vid(), 1.0)

    def test_demand_maps_cpu_vid_only(self):
        self.assertEqual(demand({'visible': True, 'cpu': ['Voltage'], 'gpu': []}), ({'cpu_voltage_v'}, set()))
        self.assertEqual(demand({'visible': True, 'cpu': [], 'gpu': ['Voltage']}), (set(), set()))


if __name__ == '__main__':
    unittest.main()
