# Linux source profiles

Source profiles select an OEM performance mode when the laptop's power source
changes. They are disabled until the user configures a nonempty source mapping.
The implementation does not migrate older unused `profile_*` preferences into
active automation. Store a new `source_profiles` mapping (for example JSON in
QSettings) and use an empty mapping for installations that have not opted in.

The original Windows profile order from `Core/Mode/ProfileManager.cs` is preserved:
Quiet, Balanced, Performance, Turbo, Eco. Configure any subset of AC, USB-C and
Battery. Unconfigured sources do not inherit a default or write a mode.

## Detection

`detect_source(root='/sys')` reads `/sys/class/power_supply/*`:

- An online `Mains` supply identifies AC and takes precedence over USB.
- An online USB-family supply identifies USB-C. This includes generic `USB` with
  `usb_type` like `[C] PD PD_PPS`, plus USB_C/USB_PD-family supply types.
- Battery requires a real non-absent Battery supply reporting Discharging, with no
  online or ambiguous external supply. Conflicting Charging/Discharging batteries
  remain Unknown.
- Missing, unreadable, malformed or indeterminate evidence returns Unknown.

The USB-C source is the kernel's USB power-supply classification; no negotiated
wattage or guarantee of adapter capacity is inferred. Battery charge percentage,
GPU state and mode labels do not determine the source. Detection makes no writes.

## Controller API and integration

```python
from source_profiles import SourceProfiles, detect_source
from hardware import MODES

controller = SourceProfiles({})  # no automation for an unconfigured installation
controller.configure({'AC': 'Performance', 'USB-C': 'Balanced', 'Battery': 'Eco'})
source = detect_source()
# Supply the current performance mode name.
decision = controller.poll(source, current_mode='Balanced')
if decision is not None:
    # Caller uses its existing verified hardware command; module itself never writes.
    command_mode = MODES[decision]

# For user-selected mode buttons/hotkeys, before applying their verified command:
controller.manual_override('Turbo')
```

The return value is an exact name accepted by `hardware.MODES`, or `None`. Callers
whose telemetry stores numeric mode strings must first map them back to names:
`{str(code): name for name, code in MODES.items()}.get(current_mode_code)`.
`SOURCE_PROFILE_NAMES` exposes the original ordered tuple. Unsupported names or
source keys raise ValueError; a failed configuration leaves the old mapping intact.

A configured first known source counts as a transition. Each transition produces
at most one decision, including when the desired mode is already selected. The
controller does not continuously force its choice or retry failed hardware writes.
A caller should surface command errors through its normal status handling.

Explicit manual choices cancel any pending source decision and hold until a known
different source is detected. Temporary Unknown polls do not release that hold or
invent a source transition. A manual choice before initial source detection also
survives that first observation.

Source decisions are driven by power-supply events. Unknown sources do not
change the current mode. Manual choices remain until a subsequent source transition.

## Verification

Fifteen deterministic tests use temporary sysfs trees and a pure controller. They
cover mains precedence, USB/PD types, missing and contradictory sources, invalid
online values, duplicates, manual holds, transient Unknown, deferred game changes,
partial mappings, runtime reconfiguration and atomic validation. No packages,
privileges, hardware writes or live power changes are needed for these tests.

Battery defaults to Eco when no explicit battery policy has been saved. An existing user-selected battery policy is preserved. The GUI initializes this default mapping; it does not force a performance change while currently on AC.
