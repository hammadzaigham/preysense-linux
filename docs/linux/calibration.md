# First-start calibration

When calibration is missing or incomplete for the current model and BIOS, the
app prompts to calibrate. Accepting runs a worker-thread mode cycle in Windows
order: Eco, Quiet, Balanced, Performance, Turbo. Already-complete mode profiles
are skipped and existing stored values are never overwritten.

AC power is required. Each mode is confirmed, allowed2.5seconds to settle, then
RAPL PL1/PL2/Tau and boost plus fan state are checked for stable readings. No CPU
or GPU benchmark runs, and calibration does not write RAPL limits. Mode changes
naturally apply firmware profiles. Custom/saved policies are paused during the
cycle, and the original mode is restored on success, failure, cancellation or
app exit. Failed/missing profiles are reported and can be retried at next startup.

These are observed firmware-initialized settings, not proof of untouched factory
defaults. They are stored per model/BIOS in ~/.local/share/PreySense/calibration.json.
NVIDIA default power is a driver-reported reference only, not an application cap.
The normal application does not cycle modes or perform recurring calibration reads.

Intel RAPL uses kernel powercap sysfs. Acer OEM controls still need the small
signed PreySense driver: it exposes bounded existing firmware methods and native
key events, without installing replacement ACPI tables. Keep the desktop app
unprivileged; running it as root does not replace those kernel interfaces.
Secure Boot validation can stay enabled with the driver signing key enrolled.
