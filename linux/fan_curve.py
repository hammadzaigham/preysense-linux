"""Windows-parity EC-style fan stages and shared delay follower.

Matches PreySense.Core FanStage / FanCurveFollower / FanCurveProfile:
advance on CPU or GPU rise, retreat when both sensors clear the previous rise,
optional 0–5 s shared delay, both fans commanded at max(cpu_duty, gpu_duty).
"""
from __future__ import annotations

import math
import time

DISABLED_TRIP = 127
CPU_MAX_RPM = 6400
GPU_MAX_RPM = 6400
STAGE_COUNT = 12
GRAPH_MIN_C = 40
GRAPH_MAX_C = 100


def rpm_to_duty(rpm: int, max_rpm: int = CPU_MAX_RPM) -> int:
    return max(0, min(100, int(round(max(0, min(max_rpm, int(rpm))) * 100.0 / max_rpm))))


def duty_to_rpm(duty: int, max_rpm: int = CPU_MAX_RPM) -> int:
    return max(0, min(max_rpm, int(round(max(0, min(100, int(duty))) * max_rpm / 100.0))))


def _stage(cpu_rise, gpu_rise, cpu_rpm, gpu_rpm, cpu_fall=0, gpu_fall=0):
    return {
        'CpuTempC': int(cpu_rise),
        'GpuTempC': int(gpu_rise),
        'CpuDutyPercent': rpm_to_duty(cpu_rpm, CPU_MAX_RPM),
        'GpuDutyPercent': rpm_to_duty(gpu_rpm, GPU_MAX_RPM),
        'CpuRiseC': int(cpu_rise),
        'GpuRiseC': int(gpu_rise),
        'CpuFallC': int(cpu_fall),
        'GpuFallC': int(gpu_fall),
        'CpuTargetRpm': int(cpu_rpm),
        'GpuTargetRpm': int(gpu_rpm),
    }


# Recovered ZBJ-KQ EC 1.08 tables (Quiet/Eco share one table).
_QUIET_ECO = (
    _stage(57, 57, 0, 0),
    _stage(64, 62, 1800, 1850, 40, 40),
    _stage(70, 66, 1970, 1980, 56, 56),
    _stage(76, 71, 2150, 2150, 65, 61),
    _stage(81, 75, 2350, 2350, 71, 65),
    _stage(127, 80, 2550, 2550, 77, 70),
    _stage(127, 127, 2850, 2850, 127, 74),
    _stage(127, 127, 2850, 2850),
    _stage(127, 127, 2850, 2850),
    _stage(127, 127, 2850, 2850),
    _stage(127, 127, 2850, 2850),
    _stage(127, 127, 6400, 6400),
)

_BALANCED = (
    _stage(56, 50, 0, 0),
    _stage(65, 56, 1800, 1850, 40, 40),
    _stage(72, 62, 1970, 1980, 55, 51),
    _stage(78, 68, 2350, 2350, 64, 57),
    _stage(84, 73, 2550, 2550, 71, 63),
    _stage(89, 77, 3180, 3170, 77, 69),
    _stage(127, 127, 3600, 3600, 83, 74),
    _stage(127, 127, 3600, 3600),
    _stage(127, 127, 3600, 3600),
    _stage(127, 127, 3600, 3600),
    _stage(127, 127, 3600, 3600),
    _stage(127, 127, 6400, 6400),
)

_PERFORMANCE = (
    _stage(50, 50, 0, 0),
    _stage(54, 56, 1970, 1980, 40, 40),
    _stage(60, 61, 2350, 2350, 51, 51),
    _stage(65, 66, 2550, 2550, 55, 57),
    _stage(70, 71, 3180, 3170, 61, 62),
    _stage(75, 76, 3900, 3900, 66, 67),
    _stage(127, 127, 4350, 4350, 71, 72),
    _stage(127, 127, 4350, 4350),
    _stage(127, 127, 4350, 4350),
    _stage(127, 127, 4350, 4350),
    _stage(127, 127, 4350, 4350),
    _stage(127, 127, 6400, 6400),
)

_TURBO = (
    _stage(55, 52, 0, 0),
    _stage(60, 55, 2150, 2150, 40, 40),
    _stage(65, 58, 2350, 2350, 56, 53),
    _stage(70, 61, 2550, 2550, 61, 56),
    _stage(74, 64, 3180, 3170, 66, 59),
    _stage(78, 67, 3950, 3900, 71, 62),
    _stage(95, 86, 4950, 4950, 75, 65),
    _stage(127, 127, 5500, 5500, 85, 78),
    _stage(127, 127, 5500, 5500),
    _stage(127, 127, 5500, 5500),
    _stage(127, 127, 5500, 5500),
    _stage(127, 127, 6400, 6400),
)


def default_stages(mode=1):
    table = {5: _TURBO, 4: _PERFORMANCE, 0: _QUIET_ECO, 6: _QUIET_ECO}.get(int(mode), _BALANCED)
    return [dict(s) for s in table]


def normalize_stage(raw):
    if not isinstance(raw, dict):
        raise ValueError('Each fan stage must be an object')
    cpu_temp = raw.get('CpuTempC', raw.get('CpuRiseC', DISABLED_TRIP))
    gpu_temp = raw.get('GpuTempC', raw.get('GpuRiseC', DISABLED_TRIP))
    if 'CpuDutyPercent' in raw or 'GpuDutyPercent' in raw:
        cpu_duty = int(raw.get('CpuDutyPercent', 0) or 0)
        gpu_duty = int(raw.get('GpuDutyPercent', 0) or 0)
        cpu_rpm = duty_to_rpm(cpu_duty, CPU_MAX_RPM)
        gpu_rpm = duty_to_rpm(gpu_duty, GPU_MAX_RPM)
    else:
        cpu_rpm = int(raw.get('CpuTargetRpm', 0) or 0)
        gpu_rpm = int(raw.get('GpuTargetRpm', 0) or 0)
        cpu_duty = rpm_to_duty(cpu_rpm, CPU_MAX_RPM)
        gpu_duty = rpm_to_duty(gpu_rpm, GPU_MAX_RPM)
    cpu_temp = max(0, min(DISABLED_TRIP, int(cpu_temp)))
    gpu_temp = max(0, min(DISABLED_TRIP, int(gpu_temp)))
    cpu_duty = max(0, min(100, int(cpu_duty)))
    gpu_duty = max(0, min(100, int(gpu_duty)))
    return {
        'CpuTempC': cpu_temp,
        'GpuTempC': gpu_temp,
        'CpuDutyPercent': cpu_duty,
        'GpuDutyPercent': gpu_duty,
        'CpuRiseC': cpu_temp,
        'GpuRiseC': gpu_temp,
        'CpuTargetRpm': duty_to_rpm(cpu_duty, CPU_MAX_RPM),
        'GpuTargetRpm': duty_to_rpm(gpu_duty, GPU_MAX_RPM),
    }


def normalize_stages(stages, mode=1):
    result = default_stages(mode)
    if not stages:
        return result
    if not isinstance(stages, (list, tuple)) or not stages:
        raise ValueError('Fan stages must be a non-empty list')
    count = min(len(stages), STAGE_COUNT)
    for i in range(count):
        result[i] = normalize_stage(stages[i])
    # Compact storage: shorter lists end at a terminal plateau; do not restore factory tail.
    if len(stages) < STAGE_COUNT:
        terminal = dict(result[len(stages) - 1])
        terminal['CpuTempC'] = terminal['GpuTempC'] = terminal['CpuRiseC'] = terminal['GpuRiseC'] = DISABLED_TRIP
        result[len(stages) - 1] = terminal
        for i in range(len(stages), STAGE_COUNT):
            result[i] = dict(terminal)
    return result


def compact_stages(stages):
    """JSON form: reachable stages including the terminal 127/127 plateau."""
    stages = [normalize_stage(s) for s in stages]
    if not stages:
        return []
    end = len(stages)
    for i, stage in enumerate(stages):
        if stage['CpuTempC'] >= DISABLED_TRIP and stage['GpuTempC'] >= DISABLED_TRIP:
            end = i + 1
            break
    trimmed = stages[:end]
    return [{
        'CpuTempC': s['CpuTempC'],
        'GpuTempC': s['GpuTempC'],
        'CpuDutyPercent': s['CpuDutyPercent'],
        'GpuDutyPercent': s['GpuDutyPercent'],
    } for s in trimmed]


def _rise_key(gpu):
    return 'GpuTempC' if gpu else 'CpuTempC'


def _duty_key(gpu):
    return 'GpuDutyPercent' if gpu else 'CpuDutyPercent'


def build_graph(stages, gpu=False):
    """Windows FanCurveWindow.BuildGraph: visible stage points for one sensor."""
    stages = normalize_stages(stages)
    rise_key = _rise_key(gpu)
    duty_key = _duty_key(gpu)
    reachable = []
    for i in range(len(stages)):
        if i > 0 and stages[i - 1][rise_key] >= DISABLED_TRIP:
            break
        reachable.append(i)
    lead_in = stages[0][duty_key] if reachable else 0
    stage_indices, temperatures, duties = [], [], []
    for stage_index in reachable:
        if stage_index == 0:
            continue
        if stages[stage_index - 1][rise_key] >= DISABLED_TRIP:
            continue
        entry = max(GRAPH_MIN_C, min(GRAPH_MAX_C, stages[stage_index - 1][rise_key]))
        if temperatures and entry <= temperatures[-1]:
            entry = min(GRAPH_MAX_C, temperatures[-1] + 1)
        if entry > GRAPH_MAX_C:
            continue
        stage_indices.append(stage_index)
        temperatures.append(entry)
        duties.append(stages[stage_index][duty_key])
    return stage_indices, temperatures, duties, lead_in


def apply_entry_temperatures(stages, stage_indices, entry_celsius, gpu=False):
    """Windows FanStage.ApplyEntryTemperatures for one sensor channel."""
    if not stage_indices or len(stage_indices) != len(entry_celsius):
        return stages
    stages = [dict(s) for s in normalize_stages(stages)]
    rise_key = _rise_key(gpu)
    temps = [max(GRAPH_MIN_C, min(GRAPH_MAX_C, int(t))) for t in entry_celsius]
    for i in range(1, len(temps)):
        temps[i] = max(temps[i], temps[i - 1] + 1)
    for visible, stage_index in enumerate(stage_indices):
        if stage_index <= 0 or stage_index >= len(stages):
            continue
        stages[stage_index - 1][rise_key] = temps[visible]
        stages[stage_index - 1]['CpuRiseC' if not gpu else 'GpuRiseC'] = temps[visible]
    last = stage_indices[-1]
    for i in range(last, len(stages)):
        stages[i][rise_key] = DISABLED_TRIP
        stages[i]['CpuRiseC' if not gpu else 'GpuRiseC'] = DISABLED_TRIP
    return normalize_stages(stages)


def set_stage_duty(stages, stage_index, duty, gpu=False):
    stages = [dict(s) for s in normalize_stages(stages)]
    if not 0 <= stage_index < len(stages):
        return stages
    duty = max(0, min(100, int(duty)))
    key = _duty_key(gpu)
    stages[stage_index][key] = duty
    if gpu:
        stages[stage_index]['GpuTargetRpm'] = duty_to_rpm(duty, GPU_MAX_RPM)
    else:
        stages[stage_index]['CpuTargetRpm'] = duty_to_rpm(duty, CPU_MAX_RPM)
    return normalize_stages(stages)


def duty_bounds(values, index):
    if not values or index < 0 or index >= len(values):
        return 0, 100
    low = 0 if index == 0 else values[index - 1]
    high = 100 if index == len(values) - 1 else values[index + 1]
    return (low, high) if low <= high else (high, low)


def temperature_bounds(temperatures, index):
    if not temperatures or index < 0 or index >= len(temperatures):
        return GRAPH_MIN_C, GRAPH_MAX_C
    low = GRAPH_MIN_C if index == 0 else temperatures[index - 1] + 1
    high = GRAPH_MAX_C if index == len(temperatures) - 1 else temperatures[index + 1] - 1
    if low > high:
        return temperatures[index], temperatures[index]
    return low, high


def enforce_nondecreasing(values):
    if not values:
        return values
    values = list(values)
    values[0] = max(0, min(100, values[0]))
    for i in range(1, len(values)):
        values[i] = max(values[i - 1], min(100, values[i]))
    return values


class FanCurveFollower:
    def __init__(self):
        self._stage = None
        self._pending_stage = None
        self._pending_since = 0

    def reset(self):
        self._stage = None
        self._pending_stage = None
        self._pending_since = 0

    def evaluate(self, cpu_temp, gpu_temp, stages, delay_seconds=0, now_ms=None):
        if now_ms is None:
            now_ms = int(time.monotonic() * 1000)
        stages = normalize_stages(stages)
        if not stages:
            return 0, 0, 0
        stage = 0 if self._stage is None else max(0, min(len(stages) - 1, self._stage))
        desired = stage
        while desired < len(stages) - 1 and self._should_advance(cpu_temp, gpu_temp, stages[desired]):
            desired += 1
        while desired > 0 and self._should_retreat(cpu_temp, gpu_temp, stages, desired):
            desired -= 1
        delay = max(0, min(5, int(delay_seconds)))
        if delay <= 0 or desired == stage:
            self._pending_stage = None
            self._stage = desired
        else:
            if self._pending_stage != desired:
                self._pending_stage = desired
                self._pending_since = now_ms
            if now_ms - self._pending_since >= delay * 1000:
                self._stage = desired
                self._pending_stage = None
        applied = 0 if self._stage is None else max(0, min(len(stages) - 1, self._stage))
        current = stages[applied]
        duty = max(current['CpuDutyPercent'], current['GpuDutyPercent'])
        return duty, duty, applied

    @staticmethod
    def _should_advance(cpu, gpu, stage):
        cpu_trip = stage['CpuTempC'] < DISABLED_TRIP and cpu >= stage['CpuTempC']
        gpu_trip = stage['GpuTempC'] < DISABLED_TRIP and gpu >= stage['GpuTempC']
        return cpu_trip or gpu_trip

    @staticmethod
    def _should_retreat(cpu, gpu, stages, stage_index):
        if stage_index <= 0:
            return False
        previous = stages[stage_index - 1]
        cpu_clear = previous['CpuTempC'] >= DISABLED_TRIP or cpu < previous['CpuTempC']
        gpu_clear = previous['GpuTempC'] >= DISABLED_TRIP or gpu < previous['GpuTempC']
        return cpu_clear and gpu_clear


class FanCurve:
    """Custom fan policy backed by EC-style stages (Windows follower semantics)."""

    def __init__(self, stages=None, delay=2, mode=1):
        if stages is None:
            stages = default_stages(mode)
        if type(delay) not in (int, float) or not math.isfinite(delay) or not 0 <= float(delay) <= 5:
            raise ValueError('Delay must be 0–5 seconds')
        self.stages = normalize_stages(stages, mode)
        self.delay = int(delay)
        self._follower = FanCurveFollower()

    def reset(self):
        self._follower.reset()

    def target(self, temperature=None, now=None, cpu_temp=None, gpu_temp=None):
        """Evaluate duties. Prefer cpu_temp/gpu_temp; a single temperature drives both."""
        if cpu_temp is None and gpu_temp is None:
            if temperature is None or not math.isfinite(temperature):
                raise ValueError('Invalid temperature')
            cpu_temp = gpu_temp = float(temperature)
        cpu = float(cpu_temp if cpu_temp is not None else 0)
        gpu = float(gpu_temp if gpu_temp is not None else 0)
        if now is None:
            now_ms = int(time.monotonic() * 1000)
        elif isinstance(now, (int, float)) and now < 1e11:
            now_ms = int(float(now) * 1000)
        else:
            now_ms = int(now)
        cpu_duty, gpu_duty, _ = self._follower.evaluate(cpu, gpu, self.stages, self.delay, now_ms)
        return cpu_duty, gpu_duty

    def to_policy(self):
        return {
            'kind': 'Custom',
            'delay': self.delay,
            'stages': compact_stages(self.stages),
        }
