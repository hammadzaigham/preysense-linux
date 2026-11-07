"""Read-only power-source detection and pure opt-in OEM profile decisions.

This module never opens a writable hardware interface. The caller applies a
returned mode through its existing verified profile command and tells the
controller about explicit manual profile choices.
"""
from pathlib import Path

SOURCE_PROFILE_NAMES = ('Eco', 'Quiet', 'Balanced', 'Performance', 'Turbo')
SOURCES = ('AC', 'USB-C', 'Battery')
UNKNOWN = 'Unknown'


def _read(path):
    try: return path.read_text().strip()
    except (OSError, UnicodeError): return None


def detect_source(root=Path('/sys')):
    """Detect power from power_supply facts, never from battery percentage.

    Mains wins over USB. Online USB-family supply types include a generic USB
    supply with usb_type such as '[C] PD PD_PPS'. Missing or malformed external
    online state prevents guessing battery-only power. A discharging, non-absent
    battery is required for Battery; no supplies or unknown state stays Unknown.
    """
    try: supplies=list((Path(root)/'class/power_supply').iterdir())
    except OSError: return UNKNOWN
    mains=False;usb=False;external_uncertain=False;discharging=False;charging=False
    for supply in supplies:
        kind=_read(supply/'type');online=_read(supply/'online')
        if kind == 'Battery':
            if _read(supply/'present') == '0': continue
            status=_read(supply/'status')
            discharging |= status == 'Discharging'
            charging |= status == 'Charging'
            continue
        if online == '1':
            if kind == 'Mains': mains=True
            elif kind is not None and (kind == 'USB' or kind.startswith('USB_') or kind.startswith('USB ')): usb=True
            else: external_uncertain=True
        elif online != '0': external_uncertain=True
    if mains: return 'AC'
    if usb: return 'USB-C'
    if discharging and not charging and not external_uncertain: return 'Battery'
    return UNKNOWN


class SourceProfiles:
    """Once-per-transition decisions; defaults disable all source automation.

    configure() is explicit opt-in, not a migration of old unused preferences.
    A configured startup source counts as a transition. Manual choices hold until
    the next *known different* source, including through temporary Unknown polls.
    Source changes apply once; manual selections persist until the next change.
    """
    def __init__(self, mapping=None):
        self.mapping={};self.last_source=None;self.source=UNKNOWN
        self.pending_source=None;self.override_mode=None
        if mapping is not None: self.configure(mapping)

    @property
    def enabled(self): return bool(self.mapping)

    def configure(self, mapping):
        if not isinstance(mapping, dict): raise ValueError('Source profiles require a mapping')
        validated={}
        for source,mode in mapping.items():
            if source not in SOURCES: raise ValueError('Unknown power source')
            if mode not in SOURCE_PROFILE_NAMES: raise ValueError('Unsupported OEM profile')
            validated[source]=mode
        if validated == self.mapping: return
        self.mapping=validated
        self.pending_source=self.last_source if validated and self.override_mode is None else None

    def manual_override(self, mode):
        if mode not in SOURCE_PROFILE_NAMES: raise ValueError('Unsupported OEM profile')
        self.override_mode=mode;self.pending_source=None

    def poll(self, source, current_mode):
        if source not in (*SOURCES, UNKNOWN): raise ValueError('Unknown power source')
        self.source=source
        if source == UNKNOWN: return None
        if source != self.last_source:
            if self.last_source is not None: self.override_mode=None
            self.last_source=source
            self.pending_source=source if self.override_mode is None else None
        if not self.enabled or self.override_mode is not None: return None
        if self.pending_source != source: return None
        self.pending_source=None
        desired=self.mapping.get(source)
        return desired if desired is not None and desired != current_mode else None
