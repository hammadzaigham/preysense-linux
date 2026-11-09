import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gpu_offsets import GpuOffsets, validate, snap


class GpuOffsetsTests(unittest.TestCase):
    def test_snap_and_validate(self):
        self.assertEqual(snap(23, 100), 25)
        self.assertEqual(validate(23, 12, 18), (25, 10, 20))
        self.assertEqual(validate(0, 0), (0, 0, None))

    def test_sysfs_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'gpu_offsets_available').write_text('1\n')
            (root / 'gpu_offsets').write_text('0 10 5 15\n1 20 10 25\n')
            api = GpuOffsets(root)
            self.assertTrue(api.available)
            self.assertEqual(api.read(1), {'ct': 20, 'db': 10, 'cp': 25})

    def test_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            api = GpuOffsets(Path(folder))
            self.assertFalse(api.available)
            self.assertEqual(api.read_all(), {})
            with self.assertRaises(OSError):
                api.apply(1, 10, 5, 15)


if __name__ == '__main__':
    unittest.main()
