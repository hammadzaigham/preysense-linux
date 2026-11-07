# Installation, updates and removal

## One-command Fedora setup

Run `./linux/setup.sh` as the desktop user. `./linux/install.sh` also redirects to it for normal installation. It installs only missing required Fedora packages with weak dependencies disabled, builds/installs the hardware bridge and GUI, then sets up the per-user AcerUltraX DTS CLI/daemon. `./linux/setup.sh --check` lists missing dependencies without changes. Automatic dependencies currently support Fedora only; other distributions require equivalent Python/PySide6/QtDBus/QtSvg/QtNetwork, kernel headers, GCC/make/DKMS, KDE KScreen/KPackage, PipeWire/Pulse compatibility and WirePlumber packages.

AcerUltraX0.1.4 downloads use the fixed official x86_64 archive and pinned SHA256; only CLI/daemon files are copied, no downloaded installer is executed. Existing tuning manifests are preserved; absent tuning runs `acerultrax-cli setup`, which imports the model files from Acer. Its service autostarts as the desktop user. No Rust compiler or separate AcerUltraX GUI is required. Audio setup must run in the user's normal session so its systemd user bus is available.


NVIDIA driver installation/signing remains separate: the setup does not replace a running display driver, reboot, alter EFI partitions, or disable Secure Boot. A new machine with no enrolled signing key still requires the firmware's normal certificate-enrollment process.

## Packaging choice

The current installed layout—GUI under `/opt/preysense`, menu launcher and system/user services—is appropriate for this hardware-control app. A portable/AppImage GUI still needs a privileged host driver, permissions and audio service, so it cannot be truly self-contained. A Fedora RPM with declarative dependencies and DKMS/service hooks is now available; see [RPM installation and building](rpm.md).

## Build and install

From the repository as the normal desktop user:

```sh
./linux/install.sh
preysense
```

The installer builds `linux/kernel/preysense.ko` for the running kernel, then uses
sudo for its own files and permissions. The GUI runs as the desktop user. Never
run the GUI as root. Administrative credentials are not written to a config file,
sudo rule, service or repository artifact.

Installed files include `/opt/preysense`, `/usr/local/bin/preysense`, the desktop
launcher, `preysense-hardware.service`, the module in the current kernel's `extra`
directory, and scoped udev rules/hwdb entries. The primary desktop user's group
receives access to typed sysfs controls, selected Intel RAPL fields, the CPU boost
switch, ENEK5130 lighting and read-only Acer vendor hotkey HID access. No blanket
membership in the `input` group is added.

PreySense can start in the tray with the session. A background instance is needed
for Predator/Turbo handling, custom fan curves, software lighting
and the desktop overlay. Closing the main window keeps that instance running;
Quit exits it. A second launch activates the existing window.

## Kernel and application updates

The installer registers the OEM driver with DKMS for automatic rebuilds on
kernel updates. Matching kernel build files and a trusted signing key remain
required. Check `dkms status` after an update; rerun the installer if a build
fails. Application updates refresh the GUI/assets without replacing NVIDIA.
Secure Boot validation need not be disabled; the signed driver must be trusted.
The app does not install custom ACPI tables, OpenCore or boot-table patches.

## Remove PreySense

```sh
sudo ./linux/uninstall.sh
```

This stops/unloads the OEM bridge, restores automatic fan control when firmware
accepts the request, removes app/service/launcher/rule files, revokes additional
RAPL and boost write permissions, and removes the app's login entry. Source and
user preferences remain. The keyboard hwdb entry is removed and the saved original Predator mappings are restored in the running kernel. The backup is captured before installation; this development install migrates the two baseline values observed before its first mapping change.
The NVIDIA driver is a separate installation. AcerUltraX is independent and is
not deleted by the PreySense uninstaller.

## Remove / disable DTS processing

```sh
acerultrax-cli autostart off
```

This stops its user service and restores normal routing. The upstream tarball's
`install.sh --uninstall` removes its user binaries/menu entry. Its settings and
19 MB of model files are deliberately retained by that upstream uninstaller;
remove those only when a complete reset is intended.

### Configured RAM speed

`preysense-hardware.service` reads the protected SMBIOS Type17 configured memory
transfer rate once when the helper starts and exports only a numeric value in
`/run/preysense-memory/speed_mts` (root-owned, world-readable). The desktop app
stays unprivileged; raw DMI tables and module serials are not exposed. CPU Memory
Speed uses the user-requested MHz display label; GPU memory clock also uses MHz. Unknown firmware values remain
N/A. This is the configured boot transfer rate, not a continuously measured
memory-controller clock. No extra package is required.

## Helper startup and shutdown

Run on Startup controls boot-time startup for PreySense and its single hardware helper.
The hardware service has conditions matching the user's
autostart entry or a manual-launch marker. A manual launch starts it on demand;
Quit restores fan ownership and stops it. A narrow local active-user polkit
rule allows only start/stop of this fixed service, not other units or
arbitrary root commands. The GUI remains unprivileged. Shared audio, PipeWire and
NVIDIA services are not managed by this lifecycle. Voltage telemetry and its
MSR service have been removed. No helper polls CPU or GPU voltage.

See [kernel driver signing and key enrollment](kernel-driver-signing.md) for the Secure Boot setup steps.
