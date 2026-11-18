# Linux features and Windows differences

The retained Linux scope follows the Windows design while using supported Linux
interfaces. Removed features are not pending parity work.

## Performance modes and CPU tuning

Eco, Quiet, Balanced, Performance and Turbo use the Acer WMI bridge. The dedicated
Turbo key cycles all five modes on AC and battery. Predator opens/hides the app;
rapid Predator presses do not select Turbo. Source automation maps Eco/Quiet to
power-saver, Balanced to balanced, and Performance/Turbo to performance. The main
window shows CPU/GPU temperature and fan RPM in the Performance Mode and GPU Mode
headers while visible. One shared 1 Hz telemetry timer feeds the main window,
overlay, and Custom fans; it stops when nothing requests sensors.

CPU PL1, PL2 and Tau use standard Intel RAPL package domains. CPU boost uses
intel_pstate. Writes retain readback and transactional rollback. Startup values
are baseline observations, not application caps or proven factory defaults.
Finite Tau selections are supported; encoded endpoints require a verified time
unit and can be unavailable. Linux may report a nearby representable window.

The Tuning window matches Windows ModeSettingsWindow: Enable Tuning, global
PROCHOT offset (MSR 0x1A2 via signed `preysense.ko`), Performance Mode, CPU
Boost switch (`intel_pstate` no_turbo), CPU Power Limits, GPU Overclocking
(Core clock 0–500 MHz, Memory clock 0–2000 MHz via NVML / nvidia-settings),
GPU Power Limits (CT/DB/CP up to 255W) with apply switches, and Reset/Apply/Save.
Mode dropdown switches the active Acer profile. Master switches in Tuning Settings
(Enable CPU Boost Tuning, Enable CPU Power Limit Control, Enable GPU Power Limit Control,
Enable GPU Overclocking) dynamically toggle section visibility.
Saved per-mode CPU/GPU policies and global PROCHOT fields live in
`preysense.json` (`HardwareTuningEnabled`, `ApplyProchotOffset`, per-mode
`ApplyCpuLimits`, `ApplyGpuLimits`, `ApplyGpuClockOffsets`). Factory defaults capture automatically at
startup (ERM4-first, live RAPL settle fallback) with no consent prompt; see
[calibration](calibration.md).

### Performance / efficiency parity

| Windows behavior | Linux |
| --- | --- |
| Acer Eco/Quiet/Balanced/Performance/Turbo | Present (WMI) |
| Source profiles → power plans | Present → `power-profiles-daemon` |
| RAPL PL1/PL2/Tau apply + readback | Present (powercap) |
| CPU boost (PERFBOOSTMODE 0–6) | Partial: on/off via `no_turbo` |
| PROCHOT offset | Present (MSR via `preysense.ko`) |
| ERM4 GPU CT/DB/CP (up to 255W) | Present (signed MMIO) |
| GPU Overclocking (Core/Memory clock offsets) | Present (NVML / `nvidia-settings`) |
| Tuning master switches | Present (`TuningSettings` dialog) |
| Fan window live telemetry | Present (CPU/GPU Temp & RPM banner) |
| Automatic factory capture | Present (ERM4 or live settle) |
| Energy Saver battery toggle | Removed (Eco/Quiet + RAPL cover this) |
| Live Advanced Optimus | Absent (boot GPU modes only) |


## Fans

Auto and Max use firmware policy. Custom uses Windows-parity decoded EC boost logic:
boost increases take effect immediately on the next shared temperature sample without fan delay.
Decreases use a fixed 3°C hysteresis below the entry threshold to avoid boundary flapping.
Each fan follows its own sensor channel (CPU or GPU, falling back to CPU when GPU temperature is unavailable).
Changed boost requests are written only when values change rather than repeatedly reinitializing Custom.
Missing CPU temperature and failed writes release software control. The kernel's 8 second watchdog returns
stalled software ownership to firmware. There is no separate emergency-temperature override.
Editing a different fan profile does not switch the active mode.

## Lighting

Four-zone keyboard, logo, Mode Key (0x65), Turbo Key (0x64), and OEM USB per-key keyboards
(Acer 0x04F2, Darfon 0x0D62, Sunrex 0x05AF) use verified hardware protocols.
Hardware Static/Dynamic effects and software effects preserve the original UI ordering.
Independent logo and Mode Key modes, operating mode color synchronization, and full keyboard
synchronization are available. Mode Key "Mode" effect mirrors active Acer operating mode colors
(Eco: #10FF10, Quiet: #A0FF90, Balanced: #00AEC7, Performance: #2E09D0, Turbo: #C700FF)
with custom palette overrides stored in `preysense.json`. Per-Key USB keyboards interface directly
via hidraw using recovered vendor packet transfers. HID handles are cached and recovered after a disconnect.
The firmware timeout accepts 0–120 seconds; 0 means off. Software effects temporarily suppress that
hardware timer and use keyboard-idle timing instead. Brightness keys are left to firmware; the app does not monitor them.

## Display, GPU and platform settings

KDE refresh-rate selection and AC/battery auto selection are available. Auto,
Hybrid and NVIDIA GPU Only are firmware boot choices; crossing the NVIDIA-only
boundary asks for confirmation and restart. Linux does not provide Windows live
Advanced Optimus switching. Battery charge limit, boot sound and USB power-off
charging use bounded Acer controls. USB charging0 is displayed as Off.

## Overlay

The native Qt overlay covers Usage/Temp/Clocks/CPU VID/Power/Memory/Fan slots
with add/remove and optional graphs. FPS, GPU Voltage, Hotspot, Memory
Temperature, and PerfCap are omitted. RAM speed is the configured firmware
transfer rate with the user-requested MHz label.
[Overlay](overlay.md), [telemetry](telemetry.md).

## Background work

Settings are read at startup. User actions retain necessary readback. Idle
telemetry stops when neither the overlay nor custom fans require sensors. Power
source and native key changes are event-driven with the updated driver. Software
RGB effects retain their animation timer. [Event-driven behavior](event-driven.md).

## Battery energy saver

The Energy Saver on Battery toggle has been removed in both Windows and Linux versions.
On-battery power saving is handled by source profiles (typically Eco/Quiet → `power-profiles-daemon` `power-saver`)
plus any saved RAPL limits for that mode.

## Deliberately removed

Custom ACPI tables, PCCC/cross-throttle patches, OpenCore setup, BlueLight Shield,
LCD overdrive UI, game automation/launching, FPS/MangoHud, Acer services toggles,
Windows PERFBOOSTMODE variants (Linux keeps a boolean Boost switch), and live
Advanced Optimus mux switching are outside the Linux app. Normal Acer WMI transport remains in the small signed
driver; it does not inject replacement ACPI tables. GPU ERM4 CT/DB/CP offsets
under Secure Boot: [gpu-power-limits](gpu-power-limits.md).
