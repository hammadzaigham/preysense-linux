import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from per_key_lighting import (
    OemUsbKey,
    OemUsbHardwareMode,
    OemUsbLightingTransfer,
    OemUsbLightingProtocol,
    OemUsbLightingDevice,
)


class PerKeyLightingTests(unittest.TestCase):
    def test_catalog_and_known_products(self):
        # Acer 0117
        self.assertTrue(OemUsbLightingProtocol.is_known_product("Acer", 0x0117))
        # Darfon ba51
        self.assertTrue(OemUsbLightingProtocol.is_known_product("Darfon", 0xBA51))
        # Sunrex 767a
        self.assertTrue(OemUsbLightingProtocol.is_known_product("Sunrex", 0x767A))
        # Unknown product
        self.assertFalse(OemUsbLightingProtocol.is_known_product("Acer", 0x9999))
        self.assertFalse(OemUsbLightingProtocol.is_known_product("UnknownVendor", 0x0117))

    def test_get_keys(self):
        keys = OemUsbLightingProtocol.get_keys("Acer", 0x0117)
        self.assertGreater(len(keys), 80)
        # Check some expected key names
        names = {k.name for k in keys}
        self.assertIn("Escape", names)
        self.assertIn("Space", names)
        self.assertIn("Left Enter", names)
        self.assertNotIn("Unused", names)

    def test_payload_length(self):
        self.assertEqual(OemUsbLightingProtocol.payload_length("Acer"), 512)
        self.assertEqual(OemUsbLightingProtocol.payload_length("Darfon"), 512)
        self.assertEqual(OemUsbLightingProtocol.payload_length("Sunrex"), 504)
        with self.assertRaises(ValueError):
            OemUsbLightingProtocol.payload_length("Invalid")

    def test_build_static_frame(self):
        keys = OemUsbLightingProtocol.get_keys("Acer", 0x0117)
        max_idx = max(k.index for k in keys)
        colors = [(0, 0, 0)] * (max_idx + 1)
        # Find Escape key
        esc = next(k for k in keys if k.name == "Escape")
        colors[esc.index] = (255, 128, 64)

        frame = OemUsbLightingProtocol.build_static_frame("Acer", 0x0117, colors)
        self.assertEqual(len(frame), 512)
        offset = esc.slot * 4
        self.assertEqual(frame[offset + 1], 255)
        self.assertEqual(frame[offset + 2], 128)
        self.assertEqual(frame[offset + 3], 64)

    def test_build_transfer(self):
        keys = OemUsbLightingProtocol.get_keys("Acer", 0x0117)
        max_idx = max(k.index for k in keys)
        colors = [(10, 20, 30)] * (max_idx + 1)

        transfer = OemUsbLightingProtocol.build_transfer("Acer", 0x0117, colors, commit_value=30)
        # Begin feature report
        self.assertEqual(transfer.begin_feature_report, bytes([0, 0x12, 0, 0, 8, 0, 0, 0, 0xE5]))
        # 512 bytes / 64 bytes per chunk = 8 write reports
        self.assertEqual(len(transfer.body_write_reports), 8)
        for report in transfer.body_write_reports:
            self.assertEqual(len(report), 65)
            self.assertEqual(report[0], 0)  # Report ID 0
        # Commit feature report
        expected_chk = (~(0x4B + 30)) & 0xFF
        self.assertEqual(transfer.commit_feature_report, bytes([0, 8, 2, 0x33, 5, 30, 8, 1, expected_chk]))
        self.assertEqual(transfer.before_body_delay_ms, 20)
        self.assertEqual(transfer.between_writes_delay_ms, 2)
        self.assertEqual(transfer.before_commit_delay_ms, 20)

    def test_build_initialization_report(self):
        init = OemUsbLightingProtocol.build_initialization_report()
        self.assertEqual(len(init), 65)
        self.assertEqual(init[0], 0)
        self.assertEqual(init[1], 0x41)
        self.assertEqual(init[2], 1)

    def test_modes_and_build_mode_transfer(self):
        modes = OemUsbLightingProtocol.get_supported_modes("Acer", 0x0117)
        self.assertGreater(len(modes), 5)
        mode_names = [m.name for m in modes]
        self.assertIn("STATIC", mode_names)
        self.assertIn("BREATHING", mode_names)
        self.assertIn("OFF", mode_names)

        # Off mode
        off_steps = OemUsbLightingProtocol.build_mode_transfer("Acer", 0x0117, mode_id=0, color=(0, 0, 0), brightness_percent=100)
        self.assertGreater(len(off_steps), 0)

        # Breathing mode
        breathing_mode = next(m for m in modes if m.name == "BREATHING")
        steps = OemUsbLightingProtocol.build_mode_transfer(
            "Acer", 0x0117, mode_id=breathing_mode.id, color=(255, 0, 0), brightness_percent=80, speed=5
        )
        self.assertGreater(len(steps), 0)
        for s in steps:
            self.assertEqual(len(s.report), 9)

    def test_device_discovery_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hidraw_dir = root / "class" / "hidraw" / "hidraw0" / "device"
            hidraw_dir.mkdir(parents=True)
            uevent = "DRIVER=hid-generic\nHID_ID=0003:000004F2:00000117\nHID_NAME=Acer Keyboard\n"
            (hidraw_dir / "uevent").write_text(uevent)

            devices = OemUsbLightingDevice.discover(root=root)
            self.assertEqual(len(devices), 1)
            dev = devices[0]
            self.assertEqual(dev.family, "Acer")
            self.assertEqual(dev.product_id, 0x0117)
            self.assertEqual(dev.name, "Acer USB Keyboard (0117)")
            self.assertEqual(dev.path, Path("/dev/hidraw0"))

    def test_apply_colors_and_mode_mock(self):
        dev = OemUsbLightingDevice("/dev/hidraw0", "Acer", 0x0117)
        dev.write_output = MagicMock()
        dev.write_feature = MagicMock()

        keys = dev.keys
        max_idx = max(k.index for k in keys)
        colors = [(100, 150, 200)] * (max_idx + 1)

        dev.apply_colors(colors, brightness=80)
        # Should write initialization report once, then 8 body writes
        self.assertEqual(dev.write_output.call_count, 9)
        # Should write begin feature report and commit feature report
        self.assertEqual(dev.write_feature.call_count, 2)

        # Apply mode
        dev.apply_mode(2, (255, 0, 0), brightness=80)
        self.assertGreater(dev.write_feature.call_count, 2)


if __name__ == '__main__':
    unittest.main()
