"""Mode Key and Turbo Key lighting implementation.

Ported from Windows ModeKeyLighting and AcerHidLightingDevice:
- Mode Key (0x65) and Turbo Key (0x64) hardware packet protocol.
- Follow operating mode (-2) palette recovered from PHN16S-71 EC firmware:
  Eco: #10FF10, Quiet: #A0FF90, Balanced: #00AEC7, Performance: #2E09D0, Turbo: #C700FF.
- Baking of Static brightness into RGB levels (hardware ignores the brightness byte in mode 2).
- Non-default overrides persistence.
"""
import re

FOLLOW_OPERATING_MODE = -2

SLOTS = [
    (0x06, "Eco", "#10FF10"),
    (0x00, "Quiet", "#A0FF90"),
    (0x01, "Balanced", "#00AEC7"),
    (0x04, "Performance", "#2E09D0"),
    (0x05, "Turbo", "#C700FF"),
]

DEFAULT_POWER_MODE_COLORS = {s[0]: s[2] for s in SLOTS}
MODE_NAMES = {s[0]: s[1] for s in SLOTS}
NAME_TO_MODE = {s[1].lower(): s[0] for s in SLOTS}


def mode_key(power_mode):
    """Normalized 2-character hex key (e.g. 5 -> '05'). Returns None on invalid input."""
    if isinstance(power_mode, str):
        cleaned = power_mode.strip()
        if cleaned.lower() in NAME_TO_MODE:
            return f"{NAME_TO_MODE[cleaned.lower()]:02X}"
        try:
            return f"{int(cleaned, 16):02X}"
        except ValueError:
            return None
    try:
        return f"{int(power_mode):02X}"
    except (TypeError, ValueError):
        return None


def normalize_hex(value):
    """Normalize hex string to #RRGGBB format; defaults to #00E5FF on failure."""
    if not value or not isinstance(value, str):
        return "#00E5FF"
    val = value.strip()
    if val.startswith("#"):
        val = val[1:]
    if len(val) == 6 and re.fullmatch(r"[0-9a-fA-F]{6}", val):
        return f"#{val.upper()}"
    return "#00E5FF"


def hex_to_rgb(hex_str):
    """Convert hex string (#RRGGBB) to (r, g, b) tuple."""
    normalized = normalize_hex(hex_str).lstrip("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def rgb_to_hex(r, g, b):
    """Convert (r, g, b) integers to #RRGGBB format."""
    return f"#{max(0, min(255, int(r))):02X}{max(0, min(255, int(g))):02X}{max(0, min(255, int(b))):02X}"


def hex_equals(a, b):
    return normalize_hex(a).upper() == normalize_hex(b).upper()


def is_default(power_mode, color_hex):
    k = mode_key(power_mode)
    if k is None:
        return False
    mode_byte = int(k, 16)
    default = DEFAULT_POWER_MODE_COLORS.get(mode_byte)
    return default is not None and hex_equals(color_hex, default)


def color_for(power_mode, overrides=None, fallback="#00AEC7"):
    """Get active color for the given power mode, checking custom overrides first."""
    k = mode_key(power_mode) or "01"
    try:
        mode_byte = int(k, 16)
    except ValueError:
        mode_byte = 1
    if overrides and isinstance(overrides, dict):
        val = overrides.get(k) or overrides.get(mode_byte) or overrides.get(str(mode_byte))
        if val and not is_default(mode_byte, val):
            return normalize_hex(val)
    if mode_byte in DEFAULT_POWER_MODE_COLORS:
        return DEFAULT_POWER_MODE_COLORS[mode_byte]
    return normalize_hex(fallback)


def only_custom_overrides(colors):
    """Filter dictionary to retain only valid overrides differing from factory defaults."""
    if not colors or not isinstance(colors, dict):
        return {}
    result = {}
    for k, v in colors.items():
        if not k or not v:
            continue
        k_norm = mode_key(k)
        if k_norm is None:
            continue
        mode_byte = int(k_norm, 16)
        if mode_byte not in DEFAULT_POWER_MODE_COLORS:
            continue
        if is_default(mode_byte, v):
            continue
        result[f"{mode_byte:02X}"] = normalize_hex(v)
    return result


def ensure_defaults(stored=None):
    """Return dictionary with all 5 power modes present, with custom overrides merged in."""
    colors = {f"{slot[0]:02X}": slot[2] for slot in SLOTS}
    for k, v in only_custom_overrides(stored).items():
        colors[k] = v
    return colors


def bake_static_brightness(brightness, red, green, blue):
    """
    Mode Key / Turbo Key Static mode ignores the brightness byte in hardware.
    Bake brightness percentage into RGB values, reporting brightness=100.
    """
    if brightness <= 0:
        return 0, 0, 0, 0
    factor = max(0.0, min(1.0, brightness / 100.0))
    return (
        max(0, min(255, int(round(red * factor)))),
        max(0, min(255, int(round(green * factor)))),
        max(0, min(255, int(round(blue * factor)))),
        100,
    )


def build_mode_key_packet(target=0x65, mode=2, brightness=100, speed=5, direction=0,
                           red=0, green=174, blue=199):
    """
    Build the 11-byte Acer HID feature report packet for Mode Key (0x65) or Turbo Key (0x64).
    Target must be 0x64 or 0x65.
    Mask is always 0x01, 0x00 (single LED target).
    """
    if target not in (0x64, 0x65):
        raise ValueError(f"Invalid hotkey target: 0x{target:02X}")
    if brightness <= 0:
        return bytes([0xA4, target, 1, 0, 0, 0, 0, 0, 0, 1, 0])
    rep_bright = brightness
    if mode == 2:  # Static mode
        red, green, blue, rep_bright = bake_static_brightness(brightness, red, green, blue)
    return bytes([
        0xA4,
        target,
        mode,
        rep_bright,
        max(0, min(10, int(speed))),
        max(0, min(7, int(direction))),
        max(0, min(255, int(red))),
        max(0, min(255, int(green))),
        max(0, min(255, int(blue))),
        1,
        0,
    ])
