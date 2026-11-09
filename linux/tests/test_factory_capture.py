"""ERM4 automatic factory capture — no Qt."""
import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibration import Calibrator
from factory_capture import read_erm4_profiles, try_automatic_erm4


class FactoryCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        dmi = self.root / 'class/dmi/id'
        dmi.mkdir(parents=True)
        for name, value in (('sys_vendor', 'Acer'), ('product_name', 'Predator PHN16S-71'), ('bios_version', '1.0')):
            (dmi / name).write_text(value)
        self.sysfs = self.root / 'sysfs'
        self.sysfs.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_read_erm4_profiles(self):
        # mode pl1 tau pl2 ct db cp — Quiet/Balanced/Performance/Turbo/Eco
        (self.sysfs / 'factory_profiles').write_text(
            '0 45 56 115 10 5 15\n'
            '1 65 56 140 15 10 20\n'
            '4 90 56 140 25 15 25\n'
            '5 100 56 140 30 20 30\n'
            '6 35 56 90 5 0 10\n'
        )
        profiles = read_erm4_profiles(self.sysfs)
        self.assertEqual(set(profiles), {'Quiet', 'Balanced', 'Performance', 'Turbo', 'Eco'})
        self.assertEqual(profiles['Balanced']['CpuPl1Watts'], 65)
        self.assertEqual(profiles['Balanced']['GpuPowerOffsetWatts'], 15)
        self.assertEqual(profiles['Balanced']['GpuDynamicBoostWatts'], 10)

    def test_incomplete_erm4_rejected(self):
        (self.sysfs / 'factory_profiles').write_text('1 65 56 140 15 10 20\n')
        self.assertEqual(read_erm4_profiles(self.sysfs), {})

    def test_automatic_erm4_fills_calibrator(self):
        (self.sysfs / 'factory_profiles').write_text(
            '0 45 56 115 10 5 15\n'
            '1 65 56 140 15 10 20\n'
            '4 90 56 140 25 15 25\n'
            '5 100 56 140 30 20 30\n'
            '6 35 56 90 5 0 10\n'
        )
        cal = Calibrator(self.root / 'calibration.json', self.root)
        self.assertTrue(cal.needs_calibration())
        self.assertTrue(try_automatic_erm4(cal, root=self.sysfs))
        self.assertFalse(cal.needs_calibration())
        self.assertEqual(cal.cache['Eco']['CpuPl1Watts'], 35)
        self.assertEqual(cal.cache['Turbo']['GpuDynamicBoostWatts'], 20)
        saved = json.loads((self.root / 'calibration.json').read_text())
        self.assertEqual(saved['Balanced']['CpuPl2Watts'], 140)


if __name__ == '__main__':
    unittest.main()
