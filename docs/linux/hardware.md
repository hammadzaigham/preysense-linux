# Hardware interfaces and permissions

## OEM WMI bridge

`linux/kernel/preysense.c` is a small GPL-2.0-only module for PHN16S-71. The GUI is
an ordinary user process. It receives typed sysfs controls under
`/sys/devices/platform/preysense`; no arbitrary ACPI method, physical-memory
address, register or shell command is exposed.

Gaming GUID: `7A4DDFE7-5B5D-40B4-8595-4408E0CC7F56`.

| Method | Use | Input |
| --- | --- | --- |
| 5 | Sensor read | `1 | sensor_id << 8` |
| 14 | Fan behavior | Auto `0x410009`, Max `0x820009`, Manual `0xC30009` |
| 15 | Fan behavior read | CPU/GPU bitmap 9 |
| 16 | Fan duty | fan ID 1/4 plus percentage in bits 8–15 |
| 22 | Misc write | typed setting selector/value |
| 23 | Misc read | typed setting selector |

Sensor IDs: CPU temperature 1, CPU RPM 2, GPU RPM 6, GPU temperature 10. Return
status is in the low byte; sensor value is in bits 8–23. Mode selector is 11.
GPU mux selector 2 and its separate backend belong to the GPU implementation;
refer to its README rather than treating firmware staging as live switching.

Battery GUID: `79772EC5-04B1-4BFD-843C-61E7F77B6CC9`, methods 20/21. Its read response
starts with a capability bitmap, not the normal Gaming-WMI status byte. APGE GUID
`61EF69EA-865C-4BC3-A502-A0DEBA0CB531` supplies keyboard timeout and USB charging.

The OEM module serializes WMI calls. Manual fan ownership has a bounded lease;
see the feature guide for curve and watchdog behavior. No custom ACPI-table
helper is installed.

## Lighting and vendor hotkeys

ENEK5130 is HID `0018:0CF2:5130`. HIDIOCSFEATURE sends 11-byte A4 reports:

```text
A4 target effect brightness speed direction R G B zone_mask 00
```

Keyboard target is `0x21`; individual static zone masks are 1, 2, 4, 8. Logo target
is `0x83`, mask 1. Off uses effect 1. These are the same model-specific reports
used by the original Windows client. The GUI opens only the discovered matching
controller, not arbitrary user-supplied device paths.

The chassis key uses read-only access to HID `0018:1025:174B`; report `04 85 FF`
is the known Mode/Turbo form. Feature channel A0 and ordinary keyboard reports
are not interpreted as mode presses. A short debounce handles repeated reports. Predator HID fallback is deferred briefly and suppressed when the native key is held or its counter advanced, so a HID-only report is not discarded merely because the counter file exists.

The model-scoped atkbd hwdb entry maps the Predator scan codes to KEY_PROG3. An
input handler counts only that dedicated key for the GUI. A separate read-only
idle timestamp aggregates keyboard activity without storing key identities.
The GUI never opens all `/dev/input/event*`, grabs the keyboard, or joins the
system `input` group. Physical key behavior remains a separate check from an
injected event passing through the actual module and GUI.

## RAPL, CPU boost and administrative scope

The permission helper grants the install user's primary group access only to
selected package-0 RAPL limit/time fields and `intel_pstate/no_turbo`. RAPL changes
are read back and rolled back on a failed multi-domain write. Read-only group access to package-0 `energy_uj` also enables CPU package-power telemetry from energy/time deltas. Counter wrap, stale/invalid intervals and unavailable counters are handled without invented values. Sysfs units are µW
and µs; user-facing units are W and s. CPU boost is an explicit boolean with readback.

Keep this group private to users who may control hardware. No credential is saved,
no unrestricted root daemon/socket is added for the GUI, and no sudo policy is
weakened. Kernel and app licenses are installed with the application.
