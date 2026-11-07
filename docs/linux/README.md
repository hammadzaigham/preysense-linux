# PreySense for Linux documentation

This repository contains the Linux app. Windows source and documentation are available in [the original repository](https://github.com/hammadzaigham/PreySense).

The Linux port is developed and tested on an Acer Predator PHN16S-71, BIOS V1.28,
Fedora 45 KDE, kernel 7.2.15-300.fc45.x86_64. Other models are not claimed supported;
the OEM hardware bridge deliberately checks this model before loading.

- [Installation, updates and removal](installation.md)
- [Fedora RPM packages](rpm.md)
- [Features, settings and differences from Windows](features.md)
- [First-install calibration and missing-data backfill](calibration.md)
- [Linux power profile mapping](system-power.md)
- [Power-source profile automation](source-profiles.md)
- [Predator and Turbo keys](hotkeys.md)
- [Hardware interfaces and permissions](hardware.md)
- [Audio / DTS:X Ultra](audio.md)
- [Hardware overlay](overlay.md)
- [Event-driven background behavior](event-driven.md)
- [Instant windows and KDE compositor integration](instant-windows.md)
- [GPU selection confirmation](gpu-mode-dialog.md)
- [NVIDIA driver and Secure Boot diagnosis](nvidia-diagnosis.md)
- [Measured CPU/GPU telemetry](telemetry.md)
- [Mode confirmation toast](mode-toast.md)
- [UI controls and effects](ui-controls.md)
- [UI ordering audit](ui-parity-audit-antigravity.md)
- [Reviewed feature differences](parity-review-antigravity.md)
- [Development and verification](development.md)
- [Troubleshooting and recovery](troubleshooting.md)
- [Calibration and observed defaults](calibration.md)
- [Firmware parity audit](parity-audit.md)
- [GPU mode and driver notes](../../linux/README.md#gpu-modes-and-nvidia-driver)

Status is intentionally split between a verified software path, a firmware/HID
command being accepted, and independent physical confirmation. An accepted
lighting report does not prove the lid visibly changed, and injected key tests
do not prove a particular physical button emitted the expected event.

The working checkout is `/home/hammad/Development/PreySense`, branch `linux-port`.
Linux implementation is in `linux/`; shared visual assets are in `linux/assets/`.
