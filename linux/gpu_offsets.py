"""Acer ERM4 GPU CT/DB/CP offsets via the signed preysense.ko sysfs bridge.

Matches Windows AcerProfileApplyTransaction semantics: write inactive-mode
profile bytes, then activate. Secure Boot stays on when the module is MOK-signed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path('/sys/devices/platform/preysense')
MAX_CT = 100
MAX_DB = 25
MAX_CP = 100


def snap(watts, maximum):
    watts = max(0, min(int(maximum), int(watts)))
    return int(round(watts / 5.0)) * 5


def validate(ct, db, cp=None):
    ct, db = snap(ct, MAX_CT), snap(db, MAX_DB)
    if ct % 5 or db % 5 or not 0 <= ct <= MAX_CT or not 0 <= db <= MAX_DB:
        raise ValueError('GPU CT/DB must be 0–100 / 0–25 in steps of 5')
    if cp is not None:
        cp = snap(cp, MAX_CP)
        if cp % 5 or not 0 <= cp <= MAX_CP:
            raise ValueError('Platform power offset must be 0–100 in steps of 5')
    return ct, db, cp


class GpuOffsets:
    def __init__(self, root=ROOT):
        self.root = Path(root)

    @property
    def available(self):
        path = self.root / 'gpu_offsets_available'
        try:
            return path.read_text().strip() == '1'
        except OSError:
            return False

    def read_all(self):
        """Return {mode: {'ct', 'db', 'cp'}} for Quiet/Balanced/Performance/Turbo/Eco."""
        if not self.available:
            return {}
        path = self.root / 'gpu_offsets'
        try:
            lines = path.read_text().splitlines()
        except OSError as exc:
            raise OSError(f'GPU offsets unavailable: {exc}') from exc
        result = {}
        for line in lines:
            parts = line.split()
            if len(parts) != 4:
                continue
            mode, ct, db, cp = (int(p) for p in parts)
            result[mode] = {'ct': ct, 'db': db, 'cp': cp}
        return result

    def read(self, mode):
        return self.read_all().get(int(mode))

    def apply(self, mode, ct, db, cp=None):
        ct, db, cp = validate(ct, db, cp)
        if not self.available:
            raise OSError('ERM4 GPU offsets are not available on this firmware')
        path = self.root / 'gpu_offsets'
        payload = f'{int(mode)} {ct} {db}' + (f' {cp}' if cp is not None else '')
        try:
            path.write_text(payload + '\n')
        except OSError as exc:
            raise OSError(f'GPU offset apply failed: {exc}') from exc
        return self.read(mode)
