# GPU power limits on Linux (Secure Boot)

## What Windows PreySense does

Windows GPU tuning does **not** set NVIDIA’s overall TGP through NVML/`nvidia-smi -pl`.
It writes Acer **ERM4** profile-table offsets:

- `GpuPowerOffsetWatts` / CT (base delta)
- `GpuDynamicBoostWatts` / DB (Dynamic Boost)
- `PlatformPowerOffsetWatts` / CP

Those bytes are applied through the signed PreySense kernel driver with physical
MMIO, while Acer mode is briefly staged. See Windows `AcerProfileApplyTransaction`
and `docs/driver_tuning.md`.

## Linux Secure Boot path (implemented)

The signed `preysense.ko` module (MOK/DKMS, same trust path as fans/profile):

1. Maps a **bounded** ERM4 window at the PHN16S-71 Predator base (`0xFE800400`)
   only when the `"Predator"` signature is present.
2. Exposes `gpu_offsets_available` and `gpu_offsets` sysfs attributes.
3. On write (`mode ct db [cp]`), stages Acer mode (Performance↔Balanced), writes
   DB/CT/CP, verifies, waits for EC settle, reactivates the target mode, and
   rolls back on failure — matching Windows transaction order.

No `/dev/mem`, no unsigned modules, no Secure Boot off. This is ERM4 parity, not
`nvidia-smi --power-limit`.

| Approach | Secure Boot OK? | Parity with Windows? | Status |
| --- | --- | --- | --- |
| Bounded ERM4 MMIO in signed `preysense.ko` | Yes (MOK-signed DKMS) | **Yes** (CT/DB/CP) | Implemented |
| `nvidia-smi --power-limit` / NVML set power limit | Yes | **No** | Telemetry only |
| Unsigned `/dev/mem` or disable SB | No | N/A | Rejected |

## Userspace

Tuning → GPU Power Limits edits Delta (CT), Dynamic Boost (DB), and Platform
Power Limit Offset (CP). Apply/Save write the sysfs bridge when the GPU apply
switch is on. Controls stay disabled when `gpu_offsets_available` is `0`
(signature missing). Rebuild and reinstall the kernel module after pulling
these changes; re-sign for Secure Boot / MOK as with any `preysense.ko` update.

## Verification on device

1. `cat /sys/devices/platform/preysense/gpu_offsets_available` → `1`
2. `cat /sys/devices/platform/preysense/gpu_offsets` → five `mode ct db cp` lines
3. Apply from Tuning UI or `echo '1 25 15 20' > .../gpu_offsets` (as the install user)
4. Confirm readback and that Acer mode returns to the selected profile
