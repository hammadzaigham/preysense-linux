# PreySense Linux v1.0.0

Native Linux control app for Acer Predator laptops.
Developed and tested on the Acer Predator Helios Neo 16S PHN16S-71 with Fedora KDE.

## Install on Fedora 45 (RPM)

[Download PreySense 1.0.0 for Fedora 45 (x86_64)](https://github.com/hammadzaigham/preysense-linux/releases/download/v1.0.0/preysense-1.0.0-1.fc45.x86_64.rpm)

After downloading, run:

```sh
cd ~/Downloads
sudo dnf install ./preysense-1.0.0-1.fc45.x86_64.rpm
preysense-setup
preysense
```

Run `preysense-setup` as your desktop user. The development RPM package is unsigned. With Secure Boot enabled, follow the [kernel driver signing and key enrollment instructions](docs/linux/kernel-driver-signing.md).
If you already installed from source, follow the [migration instructions](docs/linux/rpm.md#existing-development-installation) first.
See [all release downloads](https://github.com/hammadzaigham/preysense-linux/releases/tag/v1.0.0).

## Install from source

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

Based on [PreySense for Windows](https://github.com/hammadzaigham/PreySense).
