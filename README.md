# PreySense Linux v1.0.0

Native Linux control app for Acer Predator laptops, retaining the PreySense Windows design.
Developed and tested on the Acer Predator Helios Neo 16S PHN16S-71 with Fedora KDE.

## Install

```sh
git clone https://github.com/hammadzaigham/preysense-linux.git
cd preysense-linux
./linux/setup.sh
preysense
```

Run setup as your desktop user. It installs missing dependencies, configures the hardware helper and prepares the audio backend. NVIDIA driver installation is separate.

## Documentation

- [Linux app and setup guide](linux/README.md)
- [Linux documentation](docs/linux/README.md)
- [Installation](docs/linux/installation.md)
- [RPM packaging](docs/linux/rpm.md)
- [Supported features](docs/linux/features.md)
- [Troubleshooting](docs/linux/troubleshooting.md)

The Windows source is retained as the design and implementation reference. Its [original README](README.windows.md) describes the Windows version, not Linux capabilities.
