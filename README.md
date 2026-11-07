# PreySense Linux

A native Linux control application for Acer Predator laptops, featuring performance modes, fan curves, CPU power limits, RGB lighting, and hardware telemetry.

Tested on the **Acer Predator Helios Neo 16S (PHN16S-71)** on Fedora KDE.

---

## Installation

### Fedora (RPM)

Download the latest RPM from [Releases](https://github.com/hammadzaigham/preysense-linux/releases/tag/v1.0.0):

```sh
cd ~/Downloads
sudo dnf install ./preysense-1.0.0-1.fc45.x86_64.rpm
preysense-setup
preysense
```

> **Secure Boot Note:** If Secure Boot is enabled, `preysense-setup` will automatically detect your key status and guide you through enrolling the driver signing key via MOK Manager. See the [Driver Signing Guide](docs/linux/kernel-driver-signing.md) for details.

### Build from Source

```sh
git clone https://github.com/hammadzaigham/preysense-linux.git
cd preysense-linux
./linux/setup.sh
preysense
```

---

## Uninstallation

### If installed via RPM

To completely remove the RPM package, DKMS kernel module, and background services:

```sh
sudo dnf remove preysense
```

*(Optional: To also remove personal settings, run `rm -rf ~/.config/PreySense`)*

### If installed from Source

Run the uninstaller script from your source folder:

```sh
sudo ./linux/uninstall.sh
```

This unloads the kernel bridge, disables system services, unregisters DKMS, removes installed binaries, and clears local configuration.

---

## Features

- **Performance Modes:** Quiet, Balanced, Performance, and Turbo modes with automatic power-source switching (AC / Battery).
- **Fan Controls:** Auto, Max, and interactive custom fan curves.
- **CPU Tuning:** Intel RAPL power limits (PL1, PL2, Tau) and Turbo Boost toggle.
- **RGB Lighting:** 4-zone keyboard backlight and logo lighting controls, dynamic animations, and idle timeout.
- **Display & Hardware:** Refresh rate switching, battery charge limit (80%), and power-off USB charging.
- **On-Screen Metrics:** Real-time CPU/GPU temperatures, clocks, utilization, and fan RPM overlay.

---

## Documentation

- [App & Setup Guide](linux/README.md)
- [Installation Guide](docs/linux/installation.md)
- [Kernel Driver Signing & Secure Boot](docs/linux/kernel-driver-signing.md)
- [RPM Packaging](docs/linux/rpm.md)
- [Features Reference](docs/linux/features.md)
- [Troubleshooting](docs/linux/troubleshooting.md)

---

## Acknowledgments

- Based on [PreySense for Windows](https://github.com/hammadzaigham/PreySense).


