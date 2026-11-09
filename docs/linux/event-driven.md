# Event-driven background behavior

Settings and device metadata are read on startup and retained. User control
writes retain immediate readback; CPU limits refresh after a power action/mode
transition. Opening the app uses cached settings and does not rescan firmware.
Power-source changes arrive through kernel power_supply uevents. Predator and
shortcut counters use sysfs notifications through epoll with the updated driver;
older drivers retain the polling fallback. The source installer/DKMS ships the
new driver capability.

## Shared telemetry timer

There is one telemetry timer, one sample cycle per second, and one snapshot
shared by all consumers:

- Visible main window requests only CPU/GPU temperature and fan RPM for the
  section headers.
- Visible overlay requests only the metrics it currently displays.
- Custom fans independently request the temperatures they need.
- The shared timer stops when no visible consumer requests readings and Custom
  fan control needs no temperatures. A visible overlay with no selected metrics
  does not keep it running.

Hiding the main window drops its demand and resets header labels to N/A until
the next open. Sensor updates do not read battery/platform configuration,
display modes, audio status, RAPL configuration, or system power-profile D-Bus
properties. Audio/display changes refresh their own state after the
corresponding action. GPU Voltage telemetry has been removed; CPU VID remains
an overlay-only metric.

Software RGB effects retain their frame timer and keyboard-idle timeout; hardware
RGB effects run in firmware. No software lighting timer is added for hardware
modes. Fan watchdog and write readback remain enabled. Firmware changes made by
another program may not be reflected until next startup; this is intentional.
