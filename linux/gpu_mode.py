"""Acer BIOS mux and Linux GPU state; no live Windows DDS emulation.

The mux endpoint accepts OEM firmware values, not the Windows UI enum.
Reading PCI runtime state and DRM connector state does not open the GPU.
"""
import os
from pathlib import Path

FIRMWARE_MODES = {'Auto': 3, 'Hybrid': 1, 'NVIDIA GPU Only': 2}


def requires_confirmation(current, requested):
    """Only warn when crossing the dedicated NVIDIA boot-mode boundary."""
    return (requested in FIRMWARE_MODES
            and current != requested
            and 'NVIDIA GPU Only' in (current, requested))


class GpuMode:
    def __init__(self, root=Path('/sys')):
        self.root = Path(root)
        self.endpoint = self.root / 'devices/platform/preysense/gpu_mux'

    @staticmethod
    def read(path):
        try:
            return path.read_text().strip()
        except OSError:
            return None

    def devices(self):
        result = []
        for device in sorted((self.root / 'bus/pci/devices').glob('*')):
            if not (self.read(device / 'class') or '').startswith('0x03'):
                continue
            driver = device / 'driver'
            result.append(dict(address=device.name, vendor=self.read(device / 'vendor'),
                               driver=driver.resolve().name if driver.exists() else None,
                               runtime=self.read(device / 'power/runtime_status'),
                               boot_vga=self.read(device / 'boot_vga') == '1'))
        return result

    def snapshot(self):
        value = self.read(self.endpoint)
        firmware = next((name for name, code in FIRMWARE_MODES.items() if str(code) == value), None)
        devices = self.devices()
        panels = []
        for connector in sorted((self.root / 'class/drm').glob('card*-eDP-*')):
            if self.read(connector / 'enabled') == 'enabled':
                card = connector.name.split('-')[0]
                vendor = self.read(self.root / 'class/drm' / card / 'device/vendor')
                panels.append('NVIDIA' if vendor == '0x10de' else 'Intel' if vendor == '0x8086' else vendor or 'Unknown')
        nvidia = next((d for d in devices if d['vendor'] == '0x10de'), None)
        # Do not offer a discrete-only boot when NVIDIA has no bound driver.
        usable = bool(nvidia and nvidia['driver'] in ('nvidia', 'nouveau'))
        writable = firmware is not None and os.access(self.endpoint, os.W_OK)
        return dict(firmware=firmware, writable=writable, devices=devices,
                    panel=' / '.join(panels) or 'Unknown',
                    discrete_available=writable and usable,
                    live_switching=False,
                    description='Firmware boot setting; restart required after changes. Advanced Optimus live switching is unavailable on this Linux backend.')

    def stage(self, mode):
        if mode not in FIRMWARE_MODES:
            raise ValueError('Unsupported GPU mode')
        state = self.snapshot()
        if not state['writable']:
            raise RuntimeError('GPU mux unavailable or permission missing; reinstall the hardware bridge')
        if mode == 'NVIDIA GPU Only' and not state['discrete_available']:
            raise RuntimeError('No working discrete graphics driver detected')
        self.endpoint.write_text(str(FIRMWARE_MODES[mode]))
        if self.read(self.endpoint) != str(FIRMWARE_MODES[mode]):
            raise RuntimeError('GPU firmware readback mismatch; requested boot setting was not confirmed')
        return f'{mode} saved in firmware. Restart the laptop to apply; the current display has not switched.'
