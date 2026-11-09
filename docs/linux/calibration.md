# Automatic factory-defaults capture

When factory CPU defaults are missing, PreySense captures them automatically at
startup — the same flow as Windows `CaptureMissingFactoryDefaultsAsync`. There
is no Later / Calibrate consent prompt.

## Preferred path (ERM4)

When the signed driver maps the Predator ERM4 table (`factory_profiles` sysfs):

1. Read all five modes (Eco → Quiet → Balanced → Performance → Turbo) as
   PL1 / Tau / PL2 / CT / DB / CP in one shot.
2. Capture global PROCHOT offset / lock / Tj-Max when MSR `0x1A2` is readable.
3. Record static RAPL package floors from the current domain when available.
4. Commit into `Tuning.FactoryDefaults` (and seed GPU offset fields).

No Acer mode switching and no RAPL writes.

## Fallback path (live modes)

If ERM4 is unavailable, the worker runs the Windows live settle cycle:

1. AC power is required for the whole cycle.
2. Custom fans and owned RAPL writes are released before switching modes.
3. Each missing mode is selected, confirmed, then allowed **2.0 s** to settle.
4. PL1/PL2/Tau (and boost when readable) must be stable across samples.
5. Successful modes for this run are held in memory and committed together when
   the cycle ends. Already-complete modes stay on disk.
6. The original performance mode is always restored.

No CPU/GPU benchmark runs, and calibration does not write RAPL limits.

## Storage

Profiles use Windows field names in:

- `~/.config/PreySense/preysense.json` → `Tuning.FactoryDefaults`
- plus a compatibility write to `~/.local/share/PreySense/calibration.json`

These are observed firmware/ERM4 values, not proof of untouched factory silicon
fuses. NVIDIA default power remains telemetry only.
