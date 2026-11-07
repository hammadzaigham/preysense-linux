"""Direct in-process NVML bindings via ctypes.

Provides sub-millisecond, zero-fork GPU telemetry and allows selectively querying
only requested fields, completely avoiding slow nvidia-smi forks.
"""
import ctypes
import os
import shutil
import subprocess

NVML_TEMPERATURE_GPU = 0
NVML_CLOCK_GRAPHICS = 0
NVML_CLOCK_MEM = 2

class _nvmlUtilization_t(ctypes.Structure):
    _fields_ = [
        ('gpu', ctypes.c_uint),
        ('memory', ctypes.c_uint),
    ]

class _nvmlMemory_t(ctypes.Structure):
    _fields_ = [
        ('total', ctypes.c_ulonglong),
        ('free', ctypes.c_ulonglong),
        ('used', ctypes.c_ulonglong),
    ]

class NvmlTelemetry:
    _instance = None

    def __init__(self):
        self.available = False
        self.lib = None
        self.dev = None
        self.name = "NVIDIA GPU"
        self._init_nvml()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_nvml(self):
        for soname in ('libnvidia-ml.so.1', 'libnvidia-ml.so'):
            try:
                self.lib = ctypes.CDLL(soname)
                break
            except OSError:
                pass
        if not self.lib:
            return

        try:
            if self.lib.nvmlInit_v2() != 0:
                return
            dev = ctypes.c_void_p()
            if self.lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev)) != 0:
                return
            self.dev = dev
            buf = ctypes.create_string_buffer(96)
            if self.lib.nvmlDeviceGetName(self.dev, buf, 96) == 0:
                self.name = buf.value.decode('utf-8', errors='ignore')
            self.available = True
        except Exception:
            self.available = False

    def read_metrics(self, requested=None):
        """Read only requested fields or all if requested is None."""
        if not self.available or not self.dev:
            return None

        req = set(requested) if requested is not None else None
        def wants(key):
            return req is None or key in req

        data = {'name': self.name}
        try:
            if wants('temperature'):
                temp = ctypes.c_uint()
                if self.lib.nvmlDeviceGetTemperature(self.dev, NVML_TEMPERATURE_GPU, ctypes.byref(temp)) == 0:
                    data['temperature'] = str(temp.value)

            if wants('usage'):
                util = _nvmlUtilization_t()
                if self.lib.nvmlDeviceGetUtilizationRates(self.dev, ctypes.byref(util)) == 0:
                    data['usage'] = str(util.gpu)

            if wants('power'):
                power = ctypes.c_uint()
                if self.lib.nvmlDeviceGetPowerUsage(self.dev, ctypes.byref(power)) == 0:
                    data['power'] = f"{power.value / 1000.0:.2f}"

            if wants('clock'):
                clock = ctypes.c_uint()
                if self.lib.nvmlDeviceGetClockInfo(self.dev, NVML_CLOCK_GRAPHICS, ctypes.byref(clock)) == 0:
                    data['clock'] = str(clock.value)

            if wants('memory_clock_mhz'):
                mem_clock = ctypes.c_uint()
                if self.lib.nvmlDeviceGetClockInfo(self.dev, NVML_CLOCK_MEM, ctypes.byref(mem_clock)) == 0:
                    data['memory_clock_mhz'] = str(mem_clock.value)

            if wants('memory_used_gb') or wants('memory_total_gb'):
                mem = _nvmlMemory_t()
                if self.lib.nvmlDeviceGetMemoryInfo(self.dev, ctypes.byref(mem)) == 0:
                    data['memory_used_gb'] = round(mem.used / (1024**3), 3)
                    data['memory_total_gb'] = round(mem.total / (1024**3), 3)

            if wants('default_power_limit_w'):
                def_limit = ctypes.c_uint()
                if self.lib.nvmlDeviceGetPowerManagementDefaultLimit(self.dev, ctypes.byref(def_limit)) == 0:
                    data['default_power_limit_w'] = round(def_limit.value / 1000.0, 1)

            if wants('max_power_limit_w'):
                min_limit = ctypes.c_uint()
                max_limit = ctypes.c_uint()
                if self.lib.nvmlDeviceGetPowerManagementLimitConstraints(self.dev, ctypes.byref(min_limit), ctypes.byref(max_limit)) == 0:
                    data['max_power_limit_w'] = round(max_limit.value / 1000.0, 1)

            return data
        except Exception:
            return None
