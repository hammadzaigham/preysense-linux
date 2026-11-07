# Linux CPU and memory telemetry

`linux/cpu_telemetry.py` reads kernel files without privilege escalation, writes,
MSR access or extra packages. Missing or unsafe measurements return `None`, so the
UI can show unavailable instead of a substituted value.

| Field | Kernel source and meaning |
| --- | --- |
| `cpu_frequency_mhz` | Mean readable `cpuN/cpufreq/scaling_cur_freq` among online logical CPUs, converted kHz to MHz. |
| `cpu_p_core_mhz` | Same frequency mean restricted to the exact CPU list from `/sys/bus/event_source/devices/cpu_core/cpus`. |
| `cpu_e_core_mhz` | Same frequency mean restricted to the exact CPU list from `/sys/bus/event_source/devices/cpu_atom/cpus`. |
| `cpu_max_core_usage` | Highest available logical CPU utilization from two `/proc/stat` samples. |
| `cpu_p_core_usage` | Mean available logical CPU utilization restricted to the PMU P-core list. |
| `cpu_e_core_usage` | Mean available logical CPU utilization restricted to the PMU E-core list. |
| `cpu_power_w` | RAPL package energy delta divided by monotonic elapsed time, with documented counter wrap handling. |
| `memory_used_gb` | `(MemTotal - MemAvailable)` from `/proc/meminfo`, converted from kernel kB to GiB. Field name retains the UI's existing GB naming. |

Frequency is the kernel's current scaling frequency, not a measured effective
clock under load. SMT threads count as logical CPUs in frequency and utilization
averages. The hybrid fields never substitute aggregate frequency/utilization or
infer core type from CPU numbering. Missing, malformed or overlapping hybrid lists
leave the affected hybrid fields unavailable. Aggregate measurements remain
independent.

Utilization sums user, nice, system, idle, iowait, irq, softirq and steal jiffies;
idle plus iowait are treated as idle. Guest fields are not added, since Linux
already includes guest time in user/nice. The first sample, unchanged counters,
negative/reset deltas, newly online CPUs and invalid or long sample intervals do
not produce invented utilization. Other valid CPUs may still contribute to the
group mean. Missing/offline CPUs lose their baseline and need two samples when
they return. A readable global online list and per-CPU online files exclude offline
CPUs from frequency and usage. An invalid global online list yields no online
measurements until it becomes valid again.

RAPL uses `package-0` from intel-rapl or intel-rapl-mmio. Counter/range/domain changes,
nonpositive time and implausible power reset or reject the sample. Read permission
failures leave power unavailable; the collector does not change permissions.

The constructor preserves its original `root`, `clock`, `max_interval` and
`max_power_w` arguments and appends optional `procroot` for isolated tests.
Tests use temporary synthetic proc/sys trees and injected time to check hybrid
lists, first samples, counter reset, offline/hotplug, bad intervals, missing files,
frequency bounds and memory availability. Two read-only samples on the development
laptop confirmed distinct P/E frequencies and usage from the real PMU lists.

## Voltage

CPU and GPU voltage telemetry, including the privileged VID reader, have been removed.
