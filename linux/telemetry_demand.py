"""Translate visible HUD choices and fan demand into explicit sensor fields."""
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


def demand(overlay, custom_fans=False):
    visible = overlay.get('visible', False)
    cpu = {CPU[m] for m in overlay.get('cpu', ()) if m in CPU} if visible else set()
    gpu = {GPU[m] for m in overlay.get('gpu', ()) if m in GPU} if visible else set()
    if custom_fans:
        cpu.add('cpu_temp')
        gpu.add('temperature')
    if 'gpu_fan' in gpu:
        cpu.add('gpu_fan')
        gpu.discard('gpu_fan')
    if 'memory_used_gb' in gpu:
        gpu.add('memory_total_gb')
    return cpu, gpu
