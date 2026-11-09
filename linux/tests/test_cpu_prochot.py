"""PROCHOT offset userspace bridge — no Qt."""
import tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpu_prochot import CpuProchot, ProchotSnapshot


class CpuProchotTests(unittest.TestCase):
    def test_read_and_apply(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'cpu_prochot').write_text('7 100 0\n')
            api = CpuProchot(root)
            snap = api.read()
            self.assertEqual(snap, ProchotSnapshot(7, 100, False))
            self.assertEqual(snap.activation_celsius, 93)
            api.apply(10)
            self.assertEqual((root / 'cpu_prochot').read_text().strip(), '10')
            (root / 'cpu_prochot').write_text('10 100 0\n')
            self.assertEqual(api.read().offset_celsius, 10)

    def test_locked_rejects_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'cpu_prochot').write_text('5 100 1\n')
            api = CpuProchot(root)
            with self.assertRaises(OSError):
                api.apply(12)

    def test_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(CpuProchot(Path(folder)).read())


if __name__ == '__main__':
    unittest.main()
