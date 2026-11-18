"""Pure packet construction and device transport for OEM Per-Key USB keyboards.

Ported from Windows OemUsbLightingProtocol, OemUsbLightingModes, and OemUsbLightingDevice.
Supports Acer (0x04f2), Darfon (0x0d62), and Sunrex (0x05af) vendor products.
"""
import errno
import gzip
import json
import os
import re
import time
from pathlib import Path

try:
    import fcntl
except ImportError:
    class _DummyFcntl:
        @staticmethod
        def ioctl(*args, **kwargs):
            return 0
    fcntl = _DummyFcntl()


class OemUsbKey:
    def __init__(self, index, name, slot):
        self.index = int(index)
        self.name = str(name)
        self.slot = int(slot)

    def __repr__(self):
        return f"OemUsbKey(index={self.index}, name='{self.name}', slot={self.slot})"


class OemUsbHardwareMode:
    def __init__(self, id, name, flags, speed_min, speed_max, brightness_min, brightness_max,
                 default_speed, default_brightness, default_direction, color_mode):
        self.id = int(id)
        self.name = str(name)
        self.flags = int(flags)
        self.speed_min = int(speed_min)
        self.speed_max = int(speed_max)
        self.brightness_min = int(brightness_min)
        self.brightness_max = int(brightness_max)
        self.default_speed = int(default_speed)
        self.default_brightness = int(default_brightness)
        self.default_direction = int(default_direction)
        self.color_mode = int(color_mode)

    @property
    def supports_speed(self):
        return bool(self.flags & 1)

    @property
    def supports_direction(self):
        return bool(self.flags & 0x0E)

    @property
    def supports_color(self):
        return bool(self.flags & 0x40)

    @property
    def supports_random_colors(self):
        return bool(self.flags & 0x80)

    def __repr__(self):
        return f"OemUsbHardwareMode(id={self.id}, name='{self.name}', flags=0x{self.flags:X})"


class OemUsbLightingTransfer:
    def __init__(self, begin_feature_report, body_write_reports, commit_feature_report,
                 before_body_delay_ms, between_writes_delay_ms, before_commit_delay_ms):
        self.begin_feature_report = bytes(begin_feature_report)
        self.body_write_reports = [bytes(r) for r in body_write_reports]
        self.commit_feature_report = bytes(commit_feature_report)
        self.before_body_delay_ms = before_body_delay_ms
        self.between_writes_delay_ms = between_writes_delay_ms
        self.before_commit_delay_ms = before_commit_delay_ms


class OemUsbFeatureStep:
    def __init__(self, report, delay_after_ms=0):
        self.report = bytes(report)
        self.delay_after_ms = int(delay_after_ms)


class OemUsbLightingProtocol:
    _catalog = None

    @classmethod
    def _load_catalog(cls):
        if cls._catalog is not None:
            return cls._catalog
        assets_dir = Path(__file__).resolve().parent / "assets"
        catalog_gz = assets_dir / "oem_usb_keyboard_layouts.json.gz"
        if not catalog_gz.exists():
            # Try repo root path
            catalog_gz = Path(__file__).resolve().parents[2] / "PreySense.Core" / "Resources" / "Rgb" / "OemUsbKeyboardLayouts.json.gz"
        with gzip.open(catalog_gz, "rt", encoding="utf-8") as f:
            data = json.load(f)

        layouts = {}
        for k in data["Acer"]["keys"]:
            layouts.setdefault("acer:0117", []).append(OemUsbKey(k["index"], k["name"], k["slot"]))
        for k in data["Darfon"]["keys"]:
            layouts.setdefault("darfon:ba51", []).append(OemUsbKey(k["index"], k["name"], k["slot"]))
        for prod, keys in data["Sunrex"].items():
            layouts[f"sunrex:{prod.lower()}"] = [OemUsbKey(k["index"], k["name"], k["slot"]) for k in keys]

        modes = {}
        for family_name, family_modes in data["Modes"].items():
            modes[family_name] = [
                OemUsbHardwareMode(
                    m["id"], m["name"], m["flags"], m["speedMin"], m["speedMax"],
                    m["brightnessMin"], m["brightnessMax"], m["defaultSpeed"],
                    m["defaultBrightness"], m["defaultDirection"], m["colorMode"]
                ) for m in family_modes
            ]

        cls._catalog = (layouts, modes)
        return cls._catalog

    @classmethod
    def layout_id(cls, family, product_id):
        return f"{family}:{product_id:04x}".lower()

    @classmethod
    def is_known_product(cls, family, product_id):
        layouts, _ = cls._load_catalog()
        return cls.layout_id(family, product_id) in layouts

    @classmethod
    def payload_length(cls, family):
        f = str(family).lower()
        if f in ("acer", "darfon"):
            return 512
        if f == "sunrex":
            return 504
        raise ValueError(f"Unknown family: {family}")

    @classmethod
    def get_layout(cls, family, product_id):
        layouts, _ = cls._load_catalog()
        lid = cls.layout_id(family, product_id)
        if lid not in layouts:
            raise KeyError(f"No layout found for {family} product 0x{product_id:04X}")
        return layouts[lid]

    @classmethod
    def get_keys(cls, family, product_id):
        layout = cls.get_layout(family, product_id)
        max_len = cls.payload_length(family)
        return [
            k for k in layout
            if k.slot >= 0 and k.slot * 4 + 3 < max_len and k.name and k.name != "Unused"
        ]

    @classmethod
    def get_supported_modes(cls, family, product_id=None):
        cls.get_layout(family, product_id) if product_id is not None else None
        _, modes = cls._load_catalog()
        fam = "Acer" if str(family).lower() == "acer" else "Darfon" if str(family).lower() == "darfon" else "Sunrex"
        return modes.get(fam, [])

    @classmethod
    def map_brightness_percent(cls, percent):
        return min(100, max(0, int(percent))) // 2

    @classmethod
    def build_static_frame(cls, family, product_id, colors):
        """
        Build per-key RGB framebuffer. colors is list of (r, g, b) tuples by key.index.
        """
        layout = cls.get_layout(family, product_id)
        max_idx = max(k.index for k in layout) if layout else 0
        if len(colors) > max_idx + 1:
            raise ValueError(f"Color count {len(colors)} exceeds layout max index {max_idx}")
        frame = bytearray(cls.payload_length(family))
        for key in layout:
            if key.index >= len(colors) or key.slot < 0 or key.slot * 4 + 3 >= len(frame) or key.name == "Unused":
                continue
            offset = key.slot * 4
            c = colors[key.index]
            r, g, b = (c[0], c[1], c[2]) if isinstance(c, (list, tuple)) else (0, 0, 0)
            frame[offset + 1] = max(0, min(255, int(r)))
            frame[offset + 2] = max(0, min(255, int(g)))
            frame[offset + 3] = max(0, min(255, int(b)))
        return bytes(frame)

    @classmethod
    def build_transfer(cls, family, product_id, colors, commit_value=30):
        if not 0 <= commit_value <= 50:
            raise ValueError("commit_value must be 0..50")
        frame = cls.build_static_frame(family, product_id, colors)
        writes = []
        for offset in range(0, len(frame), 64):
            count = min(64, len(frame) - offset)
            report = bytearray(65)  # Report ID 0, then payload bytes, padded to 65
            report[1:1 + count] = frame[offset:offset + count]
            writes.append(bytes(report))
        delay = 15 if str(family).lower() == "sunrex" else 20
        commit_report = bytes([
            0, 8, 2, 0x33, 5, commit_value, 8, 1,
            (~(0x4B + commit_value)) & 0xFF
        ])
        return OemUsbLightingTransfer(
            begin_feature_report=bytes([0, 0x12, 0, 0, 8, 0, 0, 0, 0xE5]),
            body_write_reports=writes,
            commit_feature_report=commit_report,
            before_body_delay_ms=delay,
            between_writes_delay_ms=2,
            before_commit_delay_ms=delay,
        )

    @classmethod
    def build_initialization_report(cls):
        report = bytearray(65)
        report[1] = 0x41
        report[2] = 1
        return bytes(report)

    @classmethod
    def build_mode_transfer(cls, family, product_id, mode_id, color, brightness_percent,
                            speed=None, direction=0, random_colors=False):
        supported = cls.get_supported_modes(family, product_id)
        mode = next((m for m in supported if m.id == mode_id), None)
        if mode is None:
            raise ValueError(f"Mode 0x{mode_id:02X} is not a verified {family} keyboard effect.")
        raw_speed = speed if speed is not None else mode.default_speed
        if mode.supports_speed and (raw_speed < mode.speed_min or raw_speed > mode.speed_max):
            raise ValueError(f"Speed {raw_speed} out of range ({mode.speed_min}..{mode.speed_max})")
        if not mode.supports_speed:
            raw_speed = mode.default_speed
        if direction > 7 or (not mode.supports_direction and direction != 0):
            raise ValueError(f"Invalid direction: {direction}")
        if random_colors and not mode.supports_random_colors:
            raise ValueError("Mode does not support random colors")
        brightness = cls.map_brightness_percent(brightness_percent)
        rgb = color if mode.supports_color and not random_colors else (0, 0, 0)

        def cmd(*data):
            if len(data) != 7:
                raise ValueError("Command requires 7 bytes")
            chk = (~sum(data)) & 0xFF
            return bytes([0, *data, chk])

        def begin():
            return cmd(0xB1, 0, 0, 0, 0, 0, 0)

        def reset():
            return cmd(8, 2, 0, 0, 0, 0, 0)

        def rgb_cmd():
            return cmd(0x14, 0, 0, rgb[0], rgb[1], rgb[2], 0)

        fam = str(family).lower()
        if mode_id == 0:  # Off mode
            if fam == "sunrex":
                return [OemUsbFeatureStep(cmd(8, 1, 0, 0, 0, 0, 0), 0)]
            return [
                OemUsbFeatureStep(begin(), 15),
                OemUsbFeatureStep(reset(), 15),
                OemUsbFeatureStep(cmd(0x14, 0, 0, 0, 0, 0, 0), 15),
                OemUsbFeatureStep(cmd(8, 0 if fam == "darfon" else 2, 1, 1, 0, 1, 0), 0),
            ]

        wire_speed = (10 - raw_speed) & 0xFF
        if fam == "sunrex":
            wire_dir = direction + 1 if mode_id == 3 else 0
            mode_report = cmd(8, 2, mode_id, wire_speed, brightness, 0xE0 if random_colors else 0, wire_dir)
            return [
                OemUsbFeatureStep(begin(), 15),
                OemUsbFeatureStep(reset(), 15),
                OemUsbFeatureStep(mode_report, 15),
                OemUsbFeatureStep(rgb_cmd(), 0),
            ]

        native_mode = cmd(8, 0 if fam == "darfon" else 2, mode_id, wire_speed, brightness, 1, direction + 1)
        if fam == "darfon":
            return [
                OemUsbFeatureStep(begin(), 15),
                OemUsbFeatureStep(reset(), 15),
                OemUsbFeatureStep(rgb_cmd(), 15),
                OemUsbFeatureStep(native_mode, 0),
            ]
        return [
            OemUsbFeatureStep(begin(), 15),
            OemUsbFeatureStep(rgb_cmd(), 15),
            OemUsbFeatureStep(native_mode, 0),
        ]


class OemUsbLightingDevice:
    """Linux hidraw driver for OEM Per-Key USB keyboards."""

    def __init__(self, path, family, product_id):
        self.path = Path(path)
        self.family = family
        self.product_id = product_id
        self.name = f"{family} USB Keyboard ({product_id:04X})"
        self.keys = OemUsbLightingProtocol.get_keys(family, product_id)
        self._fd = None
        self._initialized = False

    @classmethod
    def discover(cls, root=Path("/sys")):
        devices = []
        hidraw_dir = root / "class" / "hidraw"
        if not hidraw_dir.exists():
            return devices
        for path in sorted(hidraw_dir.glob("hidraw*")):
            uevent_path = path / "device" / "uevent"
            if not uevent_path.exists():
                continue
            try:
                info = uevent_path.read_text()
            except OSError:
                continue
            # Parse HID_ID: BUS:VENDOR:PRODUCT
            m = re.search(r"HID_ID=[0-9A-Fa-f]+:([0-9A-Fa-f]+):([0-9A-Fa-f]+)", info)
            if not m:
                continue
            vid = int(m.group(1), 16)
            pid = int(m.group(2), 16)
            family = None
            if vid == 0x04F2:
                family = "Acer"
            elif vid == 0x0D62:
                family = "Darfon"
            elif vid == 0x05AF:
                family = "Sunrex"
            if family is None or not OemUsbLightingProtocol.is_known_product(family, pid):
                continue
            dev_node = Path("/dev") / path.name
            devices.append(cls(dev_node, family, pid))
        return devices

    def open(self):
        if self._fd is None:
            self._fd = os.open(str(self.path), os.O_RDWR | os.O_NONBLOCK)
        return self._fd

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            self._initialized = False

    def write_feature(self, report):
        fd = self.open()
        # HIDIOCSFEATURE(9): 0xc0094806
        fcntl.ioctl(fd, 0xC0094806, report)

    def write_output(self, report):
        fd = self.open()
        padded = bytearray(65)
        padded[:len(report)] = report
        os.write(fd, bytes(padded))

    def apply_colors(self, colors, brightness=100):
        transfer = OemUsbLightingProtocol.build_transfer(
            self.family, self.product_id, colors,
            OemUsbLightingProtocol.map_brightness_percent(brightness)
        )
        if not self._initialized:
            self.write_output(OemUsbLightingProtocol.build_initialization_report())
            time.sleep(0.002)
            self._initialized = True
        self.write_feature(transfer.begin_feature_report)
        time.sleep(transfer.before_body_delay_ms / 1000.0)
        for report in transfer.body_write_reports:
            self.write_output(report)
            time.sleep(transfer.between_writes_delay_ms / 1000.0)
        time.sleep(transfer.before_commit_delay_ms / 1000.0)
        self.write_feature(transfer.commit_feature_report)
        return True

    def apply_mode(self, mode_id, color, brightness=100, speed=None, direction=0, random_colors=False):
        steps = OemUsbLightingProtocol.build_mode_transfer(
            self.family, self.product_id, mode_id, color, brightness, speed, direction, random_colors
        )
        if not self._initialized:
            self.write_output(OemUsbLightingProtocol.build_initialization_report())
            time.sleep(0.002)
            self._initialized = True
        for step in steps:
            self.write_feature(step.report)
            if step.delay_after_ms > 0:
                time.sleep(step.delay_after_ms / 1000.0)
        return True
