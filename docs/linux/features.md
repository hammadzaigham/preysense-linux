# Linux features and Windows differences

The retained Linux scope follows the Windows design while using supported Linux
interfaces. Removed features are not pending parity work.

## Performance modes and CPU tuning

Eco, Quiet, Balanced, Performance and Turbo use the Acer WMI bridge. The dedicated
Turbo key cycles all five modes on AC and battery. Predator opens/hides the app;
rapid Predator presses do not select Turbo. Source automation maps Eco/Quiet to
power-saver, Balanced to balanced, and Performance/Turbo to performance.

CPU PL1, PL2 and Tau use standard Intel RAPL package domains. CPU boost uses
intel_pstate. Writes retain readback and transactional rollback. Startup values
are baseline observations, not application caps or proven factory defaults.
Finite Tau selections are supported; encoded endpoints require a verified time
unit and can be unavailable. Linux may report a nearby representable window.

Tuning's mode dropdown switches the active mode. Saved per-mode CPU policies
follow later mode changes. Calibration cycles only missing modes in Windows
order, waits for stable readings and restores the original mode; see
[calibration](calibration.md).

## Fans

Auto and Max use firmware policy. Custom has separate monotonic CPU/GPU curves
shown from40–100°C,5°C cooling hysteresis and one shared0–5second response timer.
Both curves follow the hotter valid temperature. GPU temperature is requested
only while the GPU is already active; CPU temperature alone is used otherwise.
No fan RPM or unrelated telemetry is needed to run Custom control. Missing CPU
temperature and failed writes release software control. The kernel's8second
watchdog returns stalled software ownership to firmware. There is no separate
emergency-temperature override. Editing a different fan profile does not switch
the active mode.

## Lighting

Four-zone keyboard and logo lighting use the ENEK5130 HID interface. Hardware
Static/Dynamic effects and software effects preserve the original UI ordering.
Independent logo modes and keyboard synchronization are available. HID handles
are cached and recovered after a disconnect. The firmware timeout accepts0–120
seconds;0 means off. Software effects temporarily suppress that hardware timer
and use keyboard-idle timing instead. Hardware effects have no software timeout
fallback. Brightness keys are left to firmware; the app does not monitor them.

## Display, GPU and platform settings

KDE refresh-rate selection and AC/battery auto selection are available. Auto,
Hybrid and NVIDIA GPU Only are firmware boot choices; crossing the NVIDIA-only
boundary asks for confirmation and restart. Linux does not provide Windows live
Advanced Optimus switching. Battery charge limit, boot sound and USB power-off
charging use bounded Acer controls. USB charging0 is displayed as Off.

## Overlay

The native Qt overlay has eight paired CPU/GPU slots, optional graphs and fan
RPM. Displayed RPM rounds to the nearest100. Missing values remain N/A. CPU/GPU voltage telemetry has been removed. RAM speed is the configured firmware transfer
rate with the user-requested MHz label. No game FPS collection or launch wrapper
exists. [Overlay](overlay.md), [telemetry](telemetry.md).

## Background work

Settings are read at startup. User actions retain necessary readback. Idle
telemetry stops when neither the overlay nor custom fans require sensors. Power
source and native key changes are event-driven with the updated driver. Software
RGB effects retain their animation timer. [Event-driven behavior](event-driven.md).

## Deliberately removed

Custom ACPI tables, PCCC/cross-throttle patches, OpenCore setup, GPU offset power
controls, BlueLight Shield, LCD overdrive UI, game automation/launching, FPS,
MangoHud, Acer services toggles, extended CPU boost options and battery energy
saver toggles are outside the Linux app. Normal Acer WMI transport remains in the
small signed driver; it does not inject replacement ACPI tables.
