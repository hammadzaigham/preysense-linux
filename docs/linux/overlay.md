# Metrics overlay

The native Qt HUD follows the Windows two-row CPU/GPU design with eight slots,
optional blue/green filled graphs and60sample histories. Default slot8 is paired
CPU/GPU fan RPM. FPS, game launching and MangoHud have been removed.

Appearance settings include scale, independent background/text opacity and
horizontal/vertical position. The background defaults to50percent black. The
HUD is click-through, stays above ordinary windows and is excluded from the
taskbar. Predator+R and the settings toggle share visibility state. Quitting
PreySense closes the HUD. Desktop/compositor rules still govern fullscreen stacking.

Only visible selected metrics request telemetry. Hidden updates do not measure
fonts, resize or reposition the window. Geometry is recalculated for layout,
scale/screen/font changes or values exceeding reserved widths. Graph sampling
shares the worker's rate limit; control messages do not append extra samples.

Graphs overlay the CPU/GPU traces using a shared dynamic peak floor10, filled
areas and1.5pixel lines without glow. Newly enabled graph histories begin with
zeroes; missing graph readings are zero while their text remains N/A. Memory
graph values useMB while text usesGB. Fan text rounds to the nearest100RPM.

Zero usage/power/RPM remains a valid zero. Missing, nonfinite or invalid readings
remain N/A. CPU and GPU voltage slots and readers have been removed.
RAM speed is firmware configured transfer rate; the displayed MHz label follows
the user's requested Windows presentation. It is not a live memory clock.

On KDE Wayland, the app can use the existing XCB/XWayland backend to preserve
client-selected positioning. Explicit Qt platform selection is respected.
Screens, saved scale and edge anchors are retained; no extra compositor is installed.
See [event-driven behavior](event-driven.md) and [telemetry](telemetry.md).
