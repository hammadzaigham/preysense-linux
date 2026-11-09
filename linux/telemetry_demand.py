"""Translate consumer demand into explicit sensor fields for one shared sample cycle.

Visible main window and overlay request only what they display. Custom fans
independently request the temperatures they need. A visible overlay with no
selected metrics does not keep sampling alive.
"""
CPU = {
    'Usage': 'cpu_usage',
    'Temperature': 'cpu_temp',
    'Active Clock': 'cpu_p_core_mhz',
    'Effective Clock': 'cpu_p_core_mhz',
    'Voltage': 'cpu_voltage_v',
    'Power': 'cpu_power_w',
    'Memory': 'memory_used_gb',
    'Memory Speed': 'memory_speed_mhz',
    'Fan Speed': 'cpu_fan',
}
GPU = {
    'Usage': 'usage',
    'Temperature': 'temperature',
    'Clock': 'clock',
    'Power': 'power',
    'Power Limit': 'enforced_power_limit_w',
    'Memory': 'memory_used_gb',
    'Memory Speed': 'memory_clock_mhz',
    'Fan Speed': 'gpu_fan',
}

# Windows TelemetryDemand.MainWindow: temperatures + CPU/GPU fan RPM only.
MAIN_WINDOW_SENSORS = frozenset({'cpu_temp', 'gpu_temp', 'cpu_fan', 'gpu_fan'})


def overlay_needs_sampling(overlay):
    """True only when the overlay is visible and has at least one selected metric."""
    if not overlay.get('visible', False):
        return False
    metrics = set(overlay.get('cpu', ())) | set(overlay.get('gpu', ()))
    return bool(metrics - {'None', None, ''})


def sampling_needed(overlay, custom_fans=False, main_window=False):
    """Whether the shared 1 Hz timer should run."""
    return bool(main_window or custom_fans or overlay_needs_sampling(overlay))


def demand(overlay, custom_fans=False, main_window=False):
    """Union of sensor fields for one shared snapshot this cycle."""
    if overlay_needs_sampling(overlay):
        cpu = {CPU[m] for m in overlay.get('cpu', ()) if m in CPU}
        gpu = {GPU[m] for m in overlay.get('gpu', ()) if m in GPU}
    else:
        cpu, gpu = set(), set()
    if custom_fans:
        cpu.add('cpu_temp')
        gpu.add('temperature')
    if main_window:
        cpu |= set(MAIN_WINDOW_SENSORS)
    if 'gpu_fan' in gpu:
        cpu.add('gpu_fan')
        gpu.discard('gpu_fan')
    if 'memory_used_gb' in gpu:
        gpu.add('memory_total_gb')
    return cpu, gpu
