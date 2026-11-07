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

Run `preysense-setup` as your desktop user. The development RPM package is unsigned. With Secure Boot enabled, `preysense-setup` automatically detects Secure Boot status, checks your DKMS signing keys, and requests MOK certificate enrollment if needed. Follow the [kernel driver signing and key enrollment instructions](docs/linux/kernel-driver-signing.md) for details on the one-time reboot enrollment process.
If you already installed from source, follow the [migration instructions](docs/linux/rpm.md#existing-development-installation) first.
See [all release downloads](https://github.com/hammadzaigham/preysense-linux/releases/tag/v1.0.0).

Driver signing and DKMS module verification are integrated into `preysense-setup` (and `./linux/setup.sh`). You can also run the helper script manually at any time:
`sudo /opt/preysense/linux/sign-driver.sh` (or `sudo ./linux/sign-driver.sh` in the source checkout); see the [Secure Boot guide](docs/linux/kernel-driver-signing.md).

## Install from source

```sh
git clone https://github.com/hammadzaigham/preysense-linux.git
cd preysense-linux
./linux/setup.sh
preysense
```

Run setup as your desktop user. It installs missing dependencies and configures the hardware helper. NVIDIA driver installation is separate.

## Documentation

- [Linux app and setup guide](linux/README.md)
- [Linux documentation](docs/linux/README.md)
- [Installation](docs/linux/installation.md)
- [RPM packaging](docs/linux/rpm.md)
- [Supported features](docs/linux/features.md)
- [Troubleshooting](docs/linux/troubleshooting.md)

## Acknowledgments

- Based on [PreySense for Windows](https://github.com/hammadzaigham/PreySense).

