"""Shared telemetry demand: one sample cycle for every active consumer."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from telemetry_demand import (
    demand, MAIN_WINDOW_SENSORS, overlay_needs_sampling, sampling_needed,
)


class TelemetryDemandTests(unittest.TestCase):
    def test_hidden_requests_nothing(self):
        cpu, gpu = demand({'visible': False, 'cpu': ('Temperature',), 'gpu': ('Temperature',)})
        self.assertEqual(cpu, set())
        self.assertEqual(gpu, set())
        self.assertFalse(sampling_needed({'visible': False, 'cpu': ('Temperature',)}))

    def test_visible_overlay_with_no_metrics_does_not_sample(self):
        overlay = {'visible': True, 'cpu': (), 'gpu': ()}
        self.assertFalse(overlay_needs_sampling(overlay))
        self.assertFalse(sampling_needed(overlay))
        self.assertEqual(demand(overlay), (set(), set()))

    def test_main_window_only_temps_and_rpms(self):
        cpu, gpu = demand({'visible': False}, main_window=True)
        self.assertEqual(cpu, set(MAIN_WINDOW_SENSORS))
        self.assertEqual(gpu, set())
        self.assertTrue(sampling_needed({'visible': False}, main_window=True))

    def test_custom_fans_add_temps_without_ui(self):
        cpu, gpu = demand({'visible': False}, custom_fans=True)
        self.assertEqual(cpu, {'cpu_temp'})
        self.assertEqual(gpu, {'temperature'})
        self.assertTrue(sampling_needed({'visible': False}, custom_fans=True))

    def test_main_window_and_overlay_union(self):
        cpu, gpu = demand(
            {'visible': True, 'cpu': ('Usage', 'Fan Speed'), 'gpu': ('Power',)},
            main_window=True,
        )
        self.assertIn('cpu_usage', cpu)
        self.assertIn('cpu_fan', cpu)
        self.assertIn('cpu_temp', cpu)
        self.assertIn('power', gpu)
        self.assertTrue(sampling_needed(
            {'visible': True, 'cpu': ('Usage',), 'gpu': ()}, main_window=False))


if __name__ == '__main__':
    unittest.main()
