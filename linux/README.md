# PreySense for Linux

Native PySide6 port retaining the Windows design and the user's selected Linux
feature scope. Supported development hardware: Acer Predator PHN16S-71 BIOSV1.28,
Fedora45 KDE. The Windows design reference is available in the original PreySense repository.

```sh
./linux/setup.sh
preysense
```

Run setup as the desktop user; it installs only missing Fedora dependencies,
builds/registers the signed Acer WMI bridge with DKMS, configures scoped hardware
permissions and sets up the per-user DTS backend. The GUI runs unprivileged.
`./linux/setup.sh --check` reports dependencies without changing the system.

The small driver exposes existing Acer controls and key events; it does not inject
custom ACPI tables. RAPL uses Linux powercap sysfs. Secure Boot validation can
remain enabled when the driver's signing certificate is enrolled. Setup never
needs the GUI to run as root. NVIDIA driver setup remains separate.

The app supports performance modes, Auto/Max/Custom fans, Intel PL1/PL2/Tau and
boost, keyboard/logo lighting, firmware light timeout, refresh-rate selection,
firmware GPU mux choices, charge limit, boot sound, power-off USB charging,
DTS:X Ultra controls, tray startup, calibration and a native metrics overlay.
CPU/GPU sensors are sampled only for visible overlay metrics and custom fan
temperatures; idle settings are cached. Native key and power-source changes use
events with the updated driver.

Removed features include game automation/launching, FPS/MangoHud, Night Light,
LCD overdrive UI, custom ACPI/GPU-offset/PCCC controls and OpenCore installation.
Windows live Advanced Optimus switching has no corresponding backend here.

## Documentation

- [Full Linux guide](../docs/linux/README.md)
- [Installation and removal](../docs/linux/installation.md)
- [RPM packages](../docs/linux/rpm.md)
- [Retained features](../docs/linux/features.md)
- [Calibration](../docs/linux/calibration.md)
- [Event-driven behavior](../docs/linux/event-driven.md)
- [Hardware and permissions](../docs/linux/hardware.md)
- [Overlay](../docs/linux/overlay.md)
- [Audio](../docs/linux/audio.md)
- [Troubleshooting](../docs/linux/troubleshooting.md)
- [Development and tests](../docs/linux/development.md)
- [Release checks](REMAINING.md)

Driver readback, synthetic tests and physical confirmation are different evidence.
A successful setting write alone does not prove a visible effect or performance
increase. Calibration records observed firmware-initialized values, not guaranteed
untouched factory defaults.
