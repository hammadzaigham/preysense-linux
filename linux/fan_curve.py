"""Windows-compatible fan bands, cooling hysteresis and response delay."""
from bisect import bisect_right
import math
import time

TEMPERATURES = tuple(range(35, 101, 5))

# Windows PreySense FanCurveProfile.DefaultCurve values mapped across 35°C–100°C:
DEFAULT_CPU_DUTIES = {
    5: (20, 20, 20, 20, 35, 38, 58, 73, 73, 73, 73, 81, 100, 100),       # Turbo
    4: (20, 20, 20, 29, 35, 38, 47, 57, 64, 64, 64, 64, 100, 100),       # Performance
    0: (20, 20, 20, 20, 20, 26, 29, 32, 38, 42, 42, 42, 100, 100),       # Quiet
    6: (20, 20, 20, 20, 20, 26, 29, 32, 38, 42, 42, 42, 100, 100),       # Eco
    1: (20, 20, 20, 26, 26, 29, 35, 38, 47, 53, 53, 53, 100, 100),       # Balanced
}

DEFAULT_GPU_DUTIES = {
    5: (20, 20, 20, 20, 37, 40, 61, 77, 77, 77, 77, 86, 100, 100),       # Turbo
    4: (20, 20, 20, 31, 37, 40, 50, 61, 68, 68, 68, 68, 100, 100),       # Performance
    0: (20, 20, 20, 20, 20, 29, 31, 34, 40, 45, 45, 45, 100, 100),       # Quiet
    6: (20, 20, 20, 20, 20, 29, 31, 34, 40, 45, 45, 45, 100, 100),       # Eco
    1: (20, 20, 20, 29, 29, 31, 37, 40, 50, 56, 56, 56, 100, 100),       # Balanced
}

DEFAULT_DUTIES = DEFAULT_CPU_DUTIES[1]

def default_curve(mode=1, gpu=False):
    table = DEFAULT_GPU_DUTIES if gpu else DEFAULT_CPU_DUTIES
    return table.get(int(mode), table[1])

def validate(values):
    if len(values) != len(TEMPERATURES) or any(type(v) is not int or not 0 <= v <= 100 for v in values):
        raise ValueError('Each fan curve requires fourteen integer duties between 0 and 100')
    if any(a > b for a,b in zip(values, values[1:])):
        raise ValueError('Fan speed cannot decrease at higher temperatures')
    return tuple(values)

def interpolate(temperature, values):
    if not math.isfinite(temperature): raise ValueError('Invalid temperature')
    i = bisect_right(TEMPERATURES, temperature)
    if i == 0: return values[0]
    if i == len(values): return values[-1]
    ratio = (temperature-TEMPERATURES[i-1])/(TEMPERATURES[i]-TEMPERATURES[i-1])
    return min(100, max(0, round((values[i-1]+ratio*(values[i]-values[i-1]))/5)*5))

class FanCurve:
    """A shared band and response timer apply both fan targets together."""
    def __init__(self,cpu,gpu,delay=2):
        self.cpu, self.gpu = validate(cpu), validate(gpu)
        if not math.isfinite(delay) or not 0 <= delay <= 5: raise ValueError('Delay must be 0–5 seconds')
        self.delay = delay
        self.band = self.applied = None
        self.direction = 0
        self.since = 0

    def target(self,temperature,now=None):
        if not math.isfinite(temperature): raise ValueError('Invalid temperature')
        now = time.monotonic() if now is None else now
        band = min(100, max(40, math.floor(temperature / 5) * 5))
        if self.band is None or band > self.band or temperature <= self.band - 5:
            self.band = band
        index = (self.band - TEMPERATURES[0]) // 5
        target = self.cpu[index], self.gpu[index]
        if self.applied is None or target == self.applied:
            self.direction = 0
            self.applied = target
            return target
        direction = 1 if any(a > b for a,b in zip(target,self.applied)) else -1
        if direction != self.direction:
            self.direction, self.since = direction, now
        if now - self.since >= self.delay:
            self.applied, self.direction = target, 0
        return self.applied
