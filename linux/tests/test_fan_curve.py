import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fan_curve import (
    FanCurve, FanCurveFollower, default_stages, rpm_to_duty, CPU_MAX_RPM,
    compact_stages, build_graph,
)
class FollowerTests(unittest.TestCase):
    def balanced(self):
        return default_stages(1)

    def test_stage_zero_stays_stopped_until_rise_trip(self):
        follower = FanCurveFollower()
        stages = self.balanced()
        cpu, gpu, stage = follower.evaluate(40, 40, stages, 0, 0)
        self.assertEqual(stage, 0)
        self.assertEqual(cpu, 0)
        self.assertEqual(gpu, 0)
        cpu, gpu, stage = follower.evaluate(56, 40, stages, 0, 1000)
        self.assertEqual(stage, 1)
        shared = max(rpm_to_duty(1800, CPU_MAX_RPM), rpm_to_duty(1850, CPU_MAX_RPM))
        self.assertEqual(cpu, shared)
        self.assertEqual(gpu, shared)

    def test_gpu_rise_alone_advances_stage(self):
        follower = FanCurveFollower()
        _, _, stage = follower.evaluate(40, 50, self.balanced(), 0, 0)
        self.assertEqual(stage, 1)

    def test_retreat_requires_both_sensors_clear(self):
        follower = FanCurveFollower()
        stages = self.balanced()
        follower.evaluate(65, 56, stages, 0, 0)
        _, _, stage = follower.evaluate(65, 56, stages, 0, 1000)
        self.assertEqual(stage, 2)
        _, _, stage = follower.evaluate(50, 56, stages, 0, 2000)
        self.assertEqual(stage, 2)
        _, _, stage = follower.evaluate(60, 52, stages, 0, 3000)
        self.assertEqual(stage, 1)
        _, _, stage = follower.evaluate(40, 40, stages, 0, 4000)
        self.assertEqual(stage, 0)

    def test_shared_delay_holds_stage_change(self):
        follower = FanCurveFollower()
        stages = self.balanced()
        follower.evaluate(40, 40, stages, delay_seconds=2, now_ms=0)
        _, _, stage = follower.evaluate(56, 40, stages, delay_seconds=2, now_ms=500)
        self.assertEqual(stage, 0)
        _, _, stage = follower.evaluate(56, 40, stages, delay_seconds=2, now_ms=2499)
        self.assertEqual(stage, 0)
        _, _, stage = follower.evaluate(56, 40, stages, delay_seconds=2, now_ms=2500)
        self.assertEqual(stage, 1)

    def test_disabled_trip_does_not_advance_on_that_sensor(self):
        follower = FanCurveFollower()
        quiet = default_stages(0)
        follower.evaluate(90, 75, quiet, 0, 0)
        _, _, stage = follower.evaluate(100, 75, quiet, 0, 1000)
        self.assertLessEqual(stage, 5)
        _, _, stage = follower.evaluate(100, 80, quiet, 0, 2000)
        self.assertEqual(stage, 6)

    def test_quiet_and_eco_share_defaults(self):
        self.assertEqual(
            [s['CpuTargetRpm'] for s in default_stages(0)],
            [s['CpuTargetRpm'] for s in default_stages(6)],
        )

    def test_both_fans_use_max_duty(self):
        curve = FanCurve(stages=self.balanced(), delay=0)
        duty = curve.target(cpu_temp=56, gpu_temp=40, now=0)
        self.assertEqual(duty[0], duty[1])

    def test_policy_round_trip_stages(self):
        from mode_policies import fan_policy
        policy = fan_policy({'kind': 'Custom', 'delay': 2, 'stages': compact_stages(default_stages(1))})
        self.assertEqual(policy['kind'], 'Custom')
        self.assertTrue(policy['stages'])
        self.assertIn('CpuTempC', policy['stages'][0])

    def test_custom_policy_requires_stages(self):
        from mode_policies import fan_policy
        with self.assertRaises(ValueError):
            fan_policy({'kind': 'Custom', 'delay': 1})

    def test_build_graph_uses_entry_temps(self):
        indices, temps, duties, lead = build_graph(default_stages(1), gpu=False)
        self.assertTrue(indices)
        self.assertEqual(temps[0], 56)
        self.assertEqual(lead, 0)
        self.assertEqual(len(temps), len(duties))


if __name__ == '__main__':
    unittest.main()
