import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mode_key_lighting import (
    SLOTS,
    DEFAULT_POWER_MODE_COLORS,
    FOLLOW_OPERATING_MODE,
    mode_key,
    normalize_hex,
    hex_to_rgb,
    rgb_to_hex,
    hex_equals,
    is_default,
    color_for,
    only_custom_overrides,
    ensure_defaults,
    bake_static_brightness,
    build_mode_key_packet,
)
from hardware import Hardware


class ModeKeyLightingTests(unittest.TestCase):
    def test_slots_and_defaults(self):
        expected_slots = [
            (0x06, "Eco", "#10FF10"),
            (0x00, "Quiet", "#A0FF90"),
            (0x01, "Balanced", "#00AEC7"),
            (0x04, "Performance", "#2E09D0"),
            (0x05, "Turbo", "#C700FF"),
        ]
        self.assertEqual(SLOTS, expected_slots)
        self.assertEqual(DEFAULT_POWER_MODE_COLORS[0x06], "#10FF10")
        self.assertEqual(DEFAULT_POWER_MODE_COLORS[0x00], "#A0FF90")
        self.assertEqual(DEFAULT_POWER_MODE_COLORS[0x01], "#00AEC7")
        self.assertEqual(DEFAULT_POWER_MODE_COLORS[0x04], "#2E09D0")
        self.assertEqual(DEFAULT_POWER_MODE_COLORS[0x05], "#C700FF")

    def test_mode_key_formatting(self):
        self.assertEqual(mode_key(5), "05")
        self.assertEqual(mode_key("05"), "05")
        self.assertEqual(mode_key("turbo"), "05")
        self.assertEqual(mode_key("quiet"), "00")
        self.assertEqual(mode_key("balanced"), "01")
        self.assertEqual(mode_key("eco"), "06")
        self.assertEqual(mode_key(0x04), "04")

    def test_normalize_hex(self):
        self.assertEqual(normalize_hex("#ff0033"), "#FF0033")
        self.assertEqual(normalize_hex("10FF10"), "#10FF10")
        self.assertEqual(normalize_hex("  #A0FF90  "), "#A0FF90")
        self.assertEqual(normalize_hex("invalid"), "#00E5FF")
        self.assertEqual(normalize_hex(None), "#00E5FF")

    def test_hex_conversion(self):
        self.assertEqual(hex_to_rgb("#10FF10"), (16, 255, 16))
        self.assertEqual(rgb_to_hex(16, 255, 16), "#10FF10")
        self.assertTrue(hex_equals("#c700ff", "#C700FF"))
        self.assertFalse(hex_equals("#10FF10", "#A0FF90"))

    def test_is_default(self):
        self.assertTrue(is_default(0x05, "#C700FF"))
        self.assertTrue(is_default("05", "c700ff"))
        self.assertFalse(is_default(0x05, "#FF0000"))
        self.assertFalse(is_default(0x99, "#123456"))

    def test_color_for_defaults_and_overrides(self):
        self.assertEqual(color_for(0x06), "#10FF10")
        self.assertEqual(color_for(0x01), "#00AEC7")
        self.assertEqual(color_for(0x05), "#C700FF")

        # Custom override
        overrides = {"05": "#FF0000", "01": "#00AEC7"}  # 01 is default, shouldn't override
        self.assertEqual(color_for(0x05, overrides), "#FF0000")
        self.assertEqual(color_for(0x01, overrides), "#00AEC7")
        self.assertEqual(color_for(0x00, overrides), "#A0FF90")

    def test_only_custom_overrides(self):
        raw = {
            "05": "#FF0000",     # Custom
            "01": "#00AEC7",     # Default
            "00": "#a0ff90",     # Default (case variation)
            "invalid": "#123456",
            "06": "",
        }
        filtered = only_custom_overrides(raw)
        self.assertEqual(filtered, {"05": "#FF0000"})

    def test_ensure_defaults(self):
        stored = {"05": "#FF5500"}
        all_colors = ensure_defaults(stored)
        self.assertEqual(len(all_colors), 5)
        self.assertEqual(all_colors["05"], "#FF5500")
        self.assertEqual(all_colors["01"], "#00AEC7")
        self.assertEqual(all_colors["06"], "#10FF10")
        self.assertEqual(all_colors["00"], "#A0FF90")
        self.assertEqual(all_colors["04"], "#2E09D0")

    def test_bake_static_brightness(self):
        # 100% brightness
        self.assertEqual(bake_static_brightness(100, 200, 100, 50), (200, 100, 50, 100))
        # 50% brightness
        self.assertEqual(bake_static_brightness(50, 200, 100, 50), (100, 50, 25, 100))
        # 0% brightness
        self.assertEqual(bake_static_brightness(0, 200, 100, 50), (0, 0, 0, 0))

    def test_build_mode_key_packet(self):
        # Static mode (mode 2) on Mode Key (0x65)
        packet = build_mode_key_packet(target=0x65, mode=2, brightness=80, speed=5, direction=0,
                                      red=200, green=100, blue=50)
        self.assertEqual(len(packet), 11)
        self.assertEqual(packet[0], 0xA4)
        self.assertEqual(packet[1], 0x65)
        self.assertEqual(packet[2], 2)       # Static
        self.assertEqual(packet[3], 100)     # Baked report brightness is 100
        self.assertEqual(packet[4], 5)       # Speed
        self.assertEqual(packet[5], 0)       # Direction
        self.assertEqual(packet[6], 160)     # 200 * 0.8
        self.assertEqual(packet[7], 80)      # 100 * 0.8
        self.assertEqual(packet[8], 40)      # 50 * 0.8
        self.assertEqual(packet[9], 1)       # Mask low (1 LED)
        self.assertEqual(packet[10], 0)      # Mask high

        # Turbo Key (target 0x64)
        turbo_packet = build_mode_key_packet(target=0x64, mode=4, brightness=50, speed=8, direction=0,
                                            red=255, green=0, blue=0)
        self.assertEqual(turbo_packet[1], 0x64)
        self.assertEqual(turbo_packet[2], 4)  # Breathing
        self.assertEqual(turbo_packet[3], 50) # Breathing preserves brightness byte

        # Brightness 0
        off_packet = build_mode_key_packet(target=0x65, mode=2, brightness=0)
        self.assertEqual(off_packet[2], 1)   # Off
        self.assertEqual(off_packet[3], 0)

        # Invalid target raises
        with self.assertRaises(ValueError):
            build_mode_key_packet(target=0x21)

    def test_hardware_mode_key_lighting(self):
        h = Hardware()
        h._lighting_packets = MagicMock()
        h.mode_key_lighting((16, 255, 16), brightness=100, effect='Static')
        h._lighting_packets.assert_called_once()
        packet = h._lighting_packets.call_args[0][0][0]
        self.assertEqual(packet[0], 0xA4)
        self.assertEqual(packet[1], 0x65)
        self.assertEqual(packet[2], 2)
        self.assertEqual(packet[6], 16)
        self.assertEqual(packet[7], 255)
        self.assertEqual(packet[8], 16)

        # Invalid params raise
        with self.assertRaises(ValueError):
            h.mode_key_lighting((1, 2), brightness=100)
        with self.assertRaises(ValueError):
            h.mode_key_lighting((1, 2, 3), brightness=150)
        with self.assertRaises(ValueError):
            h.mode_key_lighting((1, 2, 3), effect='UnknownEffect')


if __name__ == '__main__':
    unittest.main()
