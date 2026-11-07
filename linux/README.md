# PreySense Linux Architecture & Setup

PreySense provides native Linux controls for Acer Predator laptops through a lightweight Qt interface and a scoped DKMS kernel driver.

---

## Quick Start

```sh
./linux/setup.sh
preysense
```

Run `./linux/setup.sh` as your normal desktop user. It installs missing dependencies, builds and registers the kernel driver with DKMS, sets up hardware permissions, and prepares the application launcher.

To verify dependencies without making changes:

```sh
./linux/setup.sh --check
```

---

## Secure Boot & Driver Signing

PreySense supports Secure Boot without requiring you to disable firmware validation:

- Both `preysense-setup` and `./linux/setup.sh` automatically check whether your kernel driver requires signing.
- You can also sign or check keys manually:

```sh
sudo ./linux/sign-driver.sh
```

If prompted to enroll a Machine Owner Key (MOK), set a temporary password, reboot into the blue MOK Manager to enroll the key, and rerun the setup command.

---

## Key Features

- **Performance Modes:** Eco, Quiet, Balanced, Performance, and Turbo modes.
- **Fan Control:** Auto, Maximum, and custom temperature-to-speed curves with 10% / 5°C grid alignment.
- **CPU Power Management:** Custom Intel RAPL limits (PL1, PL2, Tau) and Turbo Boost control.
- **Lighting:** ENEK5130 4-zone keyboard backlight and logo RGB controls with custom color presets and idle sleep timeout.
- **System Settings:** 80% battery charge limiting, boot sound toggle, and power-off USB charging.
- **Telemetry Overlay:** Minimal, hardware-accelerated desktop overlay tracking live CPU/GPU temperatures, clocks, utilization, and fan speeds.

---

## Documentation

- [Linux Documentation Hub](../docs/linux/README.md)
- [Installation Guide](../docs/linux/installation.md)
- [RPM Packages](../docs/linux/rpm.md)
- [Hardware Interfaces & Permissions](../docs/linux/hardware.md)
- [Metrics Overlay](../docs/linux/overlay.md)
- [Troubleshooting & Recovery](../docs/linux/troubleshooting.md)

