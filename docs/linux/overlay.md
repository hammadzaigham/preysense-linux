# Metrics overlay

The native Qt HUD follows the Windows two-row CPU/GPU design with dynamic
add/remove slots, optional blue/green filled graphs and 60-sample histories.
Default slots: Usage, Temperature, Effective Clock/Clock, CPU VID, Power (graph),
Memory, Memory Speed. Fan Speed remains available from the menus.

CPU Voltage is MSR-reported VID (IA32_PERF_STATUS via `cpu_vid_mv` sysfs), not
measured Vcore. FPS, GPU Voltage, Hotspot, Memory Temperature, and PerfCap are
not offered.

Appearance settings include scale, independent background/text opacity, and
horizontal/vertical position. The background defaults to 50 percent black. The
HUD is click-through, stays above ordinary windows and is excluded from the
taskbar. Predator+R and the settings toggle share visibility state. Quitting
PreySense closes the HUD.

Only visible selected metrics request telemetry. Graphs use a shared dynamic peak
floor, filled areas and 1.5 pixel lines. Fan text rounds to the nearest 100 RPM.
Zero usage/power/RPM remains a valid zero; missing readings stay N/A.

See [event-driven behavior](event-driven.md) and [telemetry](telemetry.md).
