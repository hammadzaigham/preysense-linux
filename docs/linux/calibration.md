# First-start calibration

When factory CPU defaults are missing, the app prompts to calibrate. Accepting
runs a worker-thread mode cycle in Windows order: Eco, Quiet, Balanced,
Performance, Turbo. Already-complete modes are skipped and never overwritten.

## Flow

1. AC power is required for the whole cycle.
2. Custom fans and owned RAPL writes are released before switching modes.
3. Each missing mode is selected, confirmed, then allowed **2.0 s** to settle
   (same settle window as Windows live capture).
4. PL1/PL2/Tau (and boost when readable) must be stable across samples.
5. Successful modes for this run are held in memory and committed together when
   the cycle ends, so a mid-cycle failure does not write that mode. Modes that
   already succeeded earlier remain on disk; only this run’s pending set is
   discarded on cancel or AC loss.
6. The original performance mode is always restored (with retries). Failure to
   restore is reported explicitly.

No CPU/GPU benchmark runs, and calibration does not write RAPL limits. Mode
changes apply firmware profiles only.

## Storage

Profiles use Windows field names and are stored in:

- `~/.config/PreySense/preysense.json` → `Tuning.FactoryDefaults`
- plus a compatibility write to `~/.local/share/PreySense/calibration.json`

These are observed firmware-initialized settings after mode switches, not proof
of untouched factory silicon fuses. NVIDIA default power remains telemetry only.

Intel RAPL uses kernel powercap sysfs. Acer OEM mode switching still needs the
signed PreySense driver. Secure Boot can stay enabled with the driver key
enrolled.
