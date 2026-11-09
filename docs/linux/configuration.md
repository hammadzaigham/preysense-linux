# Linux configuration (`preysense.json`)

PreySense Linux stores preferences in:

`$XDG_CONFIG_HOME/PreySense/preysense.json`  
(default `~/.config/PreySense/preysense.json`)

The file uses **SchemaVersion 2** and the same top-level sections as Windows:
`General`, `Display`, `Battery`, `Session`, `Tuning`, `Fans`, `Lighting`, `Overlay`.

## Fans

Per-mode fan settings use Windows stage objects:

```json
"Fans": {
  "Balanced": {
    "ControlMode": 2,
    "RampUpSeconds": 2,
    "Stages": [
      { "CpuTempC": 56, "GpuTempC": 50, "CpuDutyPercent": 0, "GpuDutyPercent": 0 },
      { "CpuTempC": 65, "GpuTempC": 56, "CpuDutyPercent": 28, "GpuDutyPercent": 29 }
    ]
  }
}
```

`ControlMode`: 0 Auto, 1 Max, 2 Custom. Both fans run at `max(CpuDuty, GpuDuty)`.

## Tuning / factory defaults

`General.HardwareTuningEnabled` gates the Tuning window. Global PROCHOT fields
are `ApplyProchotOffset`, `ProchotOffsetCelsius`, `FactoryProchotOffsetCelsius`,
`FactoryProchotOffsetLocked`, and `FactoryTjMaxCelsius` (not per-mode).

Per-mode slots under `Tuning.<Mode>` keep `ApplyCpuLimits` / `ApplyGpuLimits`
with Windows field names (`CpuPl1Watts`, `CpuPl2Watts`, `CpuTurboTimeLimitSeconds`,
`CpuBoost`, `GpuPowerOffsetWatts`, `GpuDynamicBoostWatts`,
`PlatformPowerOffsetWatts`). Captured factory CPU limits live under
`Tuning.FactoryDefaults`. A legacy `~/.local/share/PreySense/calibration.json`
is migrated once into this file.

## Migration

On first launch, flat `QSettings('PreySense','Linux')` keys and the old
calibration JSON are imported, then new writes go only to `preysense.json`.
