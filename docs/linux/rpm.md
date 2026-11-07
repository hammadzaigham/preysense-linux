# Fedora RPM packaging

PreySense1.0.0 builds as an x86_64 Fedora RPM plus source RPM. The app version and internal DKMS bridge2.5.0 are intentionally independent.

[Download the Fedora 45 x86_64 RPM](https://github.com/hammadzaigham/preysense-linux/releases/download/v1.0.0/preysense-1.0.0-1.fc45.x86_64.rpm).

## Build

Install Fedora rpm-build, GCC and make, then run:

```sh
python3 linux/build_rpm.py --output dist/rpm
```

The builder stages only source/assets, builds in a temporary directory, and never changes the installed app or loads a driver. Binary and source RPMs are copied to the selected output.

## Install

```sh
sudo dnf install ./preysense-1.0.0-1.fc45.x86_64.rpm
preysense-setup
preysense
```

The package declares PySide6, KDE display tools, DKMS/build dependencies, PipeWire/WirePlumber and signing tools. It installs packaged services and narrowly scoped HID rules, registers/builds the DKMS source for the running kernel, and reports failures. It does not disable Secure Boot, reboot, install NVIDIA drivers, or bundle proprietary DTS data. Enrolled module-signing credentials must already exist when Secure Boot is enabled.

Run preysense-setup as the desktop user: sudo is used only to configure that user's hardware access; pinned/checksummed AcerUltraX CLI/daemon and missing model data are set up in the user's account. Existing audio data and preferences are retained.

## Existing development installation

The development laptop has a manual /opt installation and /usr/local/bin launcher. An RPM must not silently shadow or take over those untracked files. Stop PreySense, back up its /opt tree and user preferences, and remove the manual installation using its uninstaller before migrating. Keep source and user audio data. Do not run the source uninstaller after an RPM installation; use dnf remove preysense instead.

RPM erase stops owned system services, restores the saved key map and removes its DKMS version; it retains user preferences/DTS imports. Locally generated permission overrides should be removed when no longer needed. Package signing is separate from kernel-module signing; these development RPMs are unsigned.

Validation includes a real rpmbuild binary/source build, payload/dependency/scriptlet inspection, header/payload SHA256 digest verification and a DNF dry transaction resolving only the new package. A fresh-machine install/remove and Secure Boot enrollment exercise have not been run; no live package migration was performed on the development laptop.

The development Fedora45 RPM is unsigned (no OpenPGP signature); its header and payload digests verify successfully. The dry transaction was not accepted, so it did not migrate the existing manual install.

For Secure Boot, follow the [kernel driver signing guide](kernel-driver-signing.md).
