# Event-driven background behavior

Settings and device metadata are read on startup and retained. User control
writes retain immediate readback; CPU limits refresh after a power action/mode
transition. Opening the app uses cached settings and does not rescan firmware.
Power-source changes arrive through kernel power_supply uevents. Predator and
shortcut counters use sysfs notifications through epoll with the updated driver;
older drivers retain the polling fallback. The source installer/DKMS ships the
new driver capability.

The one-second sampling timer is stopped unless a visible overlay requests
metrics or Custom fans need temperatures. Custom fans request only CPU
temperature and active-GPU temperature; the sleeping GPU is not opened. Sensor
updates do not read battery/platform configuration, display modes, audio status,
RAPL configuration, or system power-profile D-Bus properties. Audio/display
changes refresh their own state after the corresponding action. CPU and GPU voltage telemetry have been removed.

Software RGB effects retain their frame timer and keyboard-idle timeout; hardware
RGB effects run in firmware. No software lighting timer is added for hardware
modes. Fan watchdog and write readback remain enabled. Firmware changes made by
another program may not be reflected until next startup; this is intentional.
