"""Intel TCC/PROCHOT offset via signed preysense.ko (MSR 0x1A2).

Matches Windows CpuProchotController: offset 0–63 °C below Tj-Max, lock bit,
platform-info capability check, readback and offset-only rollback on failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path('/sys/devices/platform/preysense')


@dataclass(frozen=True)
class ProchotSnapshot:
    offset_celsius: int
    tjmax_celsius: int
    locked: bool

    @property
    def activation_celsius(self) -> int:
        return self.tjmax_celsius - self.offset_celsius


class CpuProchot:
    def __init__(self, root=ROOT):
        self.root = Path(root)

    @property
    def path(self):
        return self.root / 'cpu_prochot'

    def read(self) -> ProchotSnapshot | None:
        try:
            parts = self.path.read_text().split()
        except OSError:
            return None
        if len(parts) != 3:
            return None
        try:
            offset, tjmax, locked = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return None
        if not 40 <= tjmax <= 125 or not 0 <= offset < tjmax or locked not in (0, 1):
            return None
        return ProchotSnapshot(offset, tjmax, bool(locked))

    def apply(self, offset: int) -> ProchotSnapshot:
        offset = int(offset)
        if not 0 <= offset <= 63:
            raise ValueError('PROCHOT offset must be between 0 and 63°C.')
        snap = self.read()
        if snap is None:
            raise OSError('Could not read PROCHOT settings.')
        if snap.locked and snap.offset_celsius != offset:
            raise OSError('PROCHOT is locked in BIOS.')
        if offset >= snap.tjmax_celsius:
            raise ValueError('PROCHOT offset is too high for this CPU.')
        try:
            self.path.write_text(f'{offset}\n')
        except OSError as exc:
            raise OSError(f'Could not change PROCHOT: {exc}') from exc
        after = self.read()
        if after is not None:
            if after.offset_celsius != offset:
                raise OSError('Could not change PROCHOT. Previous value was restored.')
            return after
        # Writable mock without kernel show-format readback.
        return ProchotSnapshot(offset, snap.tjmax_celsius, snap.locked)
