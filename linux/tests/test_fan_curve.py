import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fan_curve import FanCurve, DEFAULT_DUTIES, interpolate

class FanCurveTests(unittest.TestCase):
    def test_reject_decreasing_curve(self):
        with self.assertRaises(ValueError): FanCurve([50,0]+[100]*12,DEFAULT_DUTIES)
    def test_follows_curve_values(self):
        c=FanCurve(DEFAULT_DUTIES,DEFAULT_DUTIES,5)
        c.target(40,0)
        c.target(100,1)
        self.assertEqual(c.target(100,6),(100,100))
    def test_symmetric_delay(self):
        c=FanCurve(DEFAULT_DUTIES,DEFAULT_DUTIES,2)
        initial=c.target(40,0)
        self.assertEqual(c.target(60,1),initial)
        raised=c.target(60,3)
        self.assertGreater(raised[0],initial[0])
        self.assertEqual(c.target(40,4),raised)
        self.assertEqual(c.target(40,6),initial)
    def test_interpolation_and_clamps(self):
        self.assertEqual(interpolate(0,DEFAULT_DUTIES),20)
        self.assertEqual(interpolate(120,DEFAULT_DUTIES),100)
        self.assertEqual(interpolate(47.5,DEFAULT_DUTIES),25)
    def test_invalid_sensor_value(self):
        for temp in (float('nan'),float('inf')):
            with self.assertRaises(ValueError): interpolate(temp,DEFAULT_DUTIES)

class WindowsFollowerTests(unittest.TestCase):
    def curve(self, delay=0):
        # Hidden legacy 35°C point followed by the Windows 40–100°C points.
        values=(20,20,20,25,30,40,50,60,70,80,90,100,100,100)
        return FanCurve(values,values,delay)

    def test_cooling_hysteresis(self):
        c=self.curve()
        for t,want in ((59,30),(60,40),(59,40),(56,40),(55,30)):
            self.assertEqual(c.target(t,0),(want,want))

    def test_same_direction_keeps_clock_and_latest_target(self):
        for temperatures, expected in (((60,65,70,75),(40,40,40,70)),
                                        ((75,70,65,60),(70,70,70,40))):
            c=self.curve(2)
            for now,(t,want) in enumerate(zip(temperatures,expected)):
                self.assertEqual(c.target(t,now),(want,want))

    def test_return_to_applied_cancels_pending(self):
        c=self.curve(5)
        for now,t,want in ((0,70,60),(1,65,60),(4,70,60),(5,65,60),(9,65,60),(10,65,50)):
            self.assertEqual(c.target(t,now),(want,want))

    def test_whole_percent_targets_and_shared_clock(self):
        cpu=(20,20,37)+(100,)*11
        gpu=(20,20,20,40)+(100,)*10
        c=FanCurve(cpu,gpu,2)
        self.assertEqual(c.target(40,0),(20,20))
        self.assertEqual(c.target(45,1),(20,20))
        self.assertEqual(c.target(50,2),(20,20))
        self.assertEqual(c.target(50,3),(100,40))
        self.assertEqual(c.target(50,4),(100,40))
        c=FanCurve(cpu,gpu,0)
        self.assertEqual(c.target(49,0),(37,20))

    def test_shared_cooling_clock_when_second_fan_changes_later(self):
        cpu=(20,20,37)+(100,)*11
        gpu=(20,20,20,40)+(100,)*10
        c=FanCurve(cpu,gpu,2)
        self.assertEqual(c.target(50,0),(100,40))
        self.assertEqual(c.target(45,1),(100,40))
        self.assertEqual(c.target(40,2),(100,40))
        self.assertEqual(c.target(40,3),(20,20))

    def test_no_emergency_override(self):
        c=FanCurve((37,)*14,(43,)*14,0)
        self.assertEqual(c.target(100,0),(37,43))

    def test_default_delay_and_new_profile_reset(self):
        self.assertEqual(FanCurve(DEFAULT_DUTIES,DEFAULT_DUTIES).delay,2)
        self.assertEqual(self.curve(5).target(75,0),(70,70))

if __name__=='__main__': unittest.main()
