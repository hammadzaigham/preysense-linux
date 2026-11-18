"""GPU Clock Tuning for PreySense Linux.

Matches PreySense.Core/Gpu/GpuClockTuning.cs and NvidiaGpuControl.ClockTuning.cs:
- Core Clock Offset: 0 to 500 MHz, step 5 MHz
- Memory Clock Offset: 0 to 2000 MHz, step 100 MHz
- Supports hardware application via direct in-process NVML (libnvidia-ml.so)
  with fallback to nvidia-settings CLI.
"""
from dataclasses import dataclass
import shutil
import subprocess
import ctypes


@dataclass(frozen=True)
class GpuClockOffsets:
    core_mhz: int
    memory_mhz: int


class GpuClockRange:
    def __init__(self, minimum_mhz: int, maximum_mhz: int, step_mhz: int = 1):
        self.minimum_mhz = minimum_mhz
        self.maximum_mhz = maximum_mhz
        self.step_mhz = step_mhz

    def contains(self, value: int) -> bool:
        return self.minimum_mhz <= value <= self.maximum_mhz

    def snap(self, value: int, step: int = None) -> int:
        s = step if step is not None else self.step_mhz
        if s <= 0:
            s = 1
        rounded = round(value / s) * s
        return max(self.minimum_mhz, min(self.maximum_mhz, rounded))


class GpuClockTuning:
    CORE_RANGE = GpuClockRange(0, 500, 5)
    MEMORY_RANGE = GpuClockRange(0, 2000, 100)
    CORE_STEP_MHZ = 5
    MEMORY_STEP_MHZ = 100

    def __init__(self, nvml=None):
        self._nvml = nvml

    def _get_nvml(self):
        if self._nvml is not None:
            return self._nvml
        try:
            from nvml_telemetry import NvmlTelemetry
            self._nvml = NvmlTelemetry.get_instance()
            return self._nvml
        except Exception:
            return None

    def is_available(self) -> bool:
        nvml = self._get_nvml()
        if nvml and getattr(nvml, 'available', False) and getattr(nvml, 'dev', None):
            return True
        if shutil.which('nvidia-settings'):
            return True
        return False

    def apply_clock_offsets(self, core_mhz: int, memory_mhz: int) -> tuple[bool, str]:
        core = self.CORE_RANGE.snap(core_mhz)
        memory = self.MEMORY_RANGE.snap(memory_mhz)

        # 1. Try direct NVML call first
        nvml = self._get_nvml()
        if nvml and getattr(nvml, 'available', False) and getattr(nvml, 'dev', None) and getattr(nvml, 'lib', None):
            lib = nvml.lib
            dev = nvml.dev
            has_core = hasattr(lib, 'nvmlDeviceSetGpcClkVfOffset')
            has_mem = hasattr(lib, 'nvmlDeviceSetMemClkVfOffset')
            if has_core or has_mem:
                try:
                    scale = 1000
                    if hasattr(lib, 'nvmlDeviceGetGpcClkVfOffsetRange'):
                        min_v = ctypes.c_int()
                        max_v = ctypes.c_int()
                        if lib.nvmlDeviceGetGpcClkVfOffsetRange(dev, ctypes.byref(min_v), ctypes.byref(max_v)) == 0:
                            if 0 < max_v.value < 5000:
                                scale = 1
                    errs = []
                    if has_core:
                        res = lib.nvmlDeviceSetGpcClkVfOffset(dev, ctypes.c_int(core * scale))
                        if res != 0:
                            errs.append(f"core offset failed ({res})")
                    if has_mem:
                        res = lib.nvmlDeviceSetMemClkVfOffset(dev, ctypes.c_int(memory * scale))
                        if res != 0:
                            errs.append(f"memory offset failed ({res})")
                    if not errs:
                        return True, "GPU clock offsets applied."
                except Exception:
                    pass

        # 2. Fall back to nvidia-settings
        cmd = shutil.which('nvidia-settings')
        if cmd:
            try:
                args = [
                    cmd,
                    '-a', f'[gpu:0]/GPUGraphicsClockOffsetAllPerformanceLevels={core}',
                    '-a', f'[gpu:0]/GPUMemoryTransferRateOffsetAllPerformanceLevels={memory * 2}'
                ]
                proc = subprocess.run(args, capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    return True, "GPU clock offsets applied."
                return False, f"nvidia-settings returned code {proc.returncode}: {proc.stderr.strip()}"
            except Exception as ex:
                return False, f"GPU clock tuning failed: {ex}"

        return False, "GPU overclocking is unavailable while the GPU is asleep or unsupported."

    def reset_clock_offsets(self) -> tuple[bool, str]:
        return self.apply_clock_offsets(0, 0)
