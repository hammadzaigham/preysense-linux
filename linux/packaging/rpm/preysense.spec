%global debug_package %{nil}
Name:           preysense
Version:        1.0.0
Release:        1%{?dist}
Summary:        Acer Predator hardware controls for Linux
License:        MIT AND GPL-2.0-only
URL:            https://github.com/hammadzaigham/preysense-linux
Source0:        %{name}-%{version}.tar.gz
BuildArch:      x86_64
BuildRequires:  gcc
BuildRequires:  make
Requires:       python3
Requires:       python3-pyside6
Requires:       dkms
Requires:       kernel-devel-matched
Requires:       gcc
Requires:       make
Requires:       kscreen
Requires:       libkscreen
Requires:       kf6-kpackage
Requires:       pipewire
Requires:       pipewire-pulseaudio
Requires:       wireplumber
Requires:       mokutil
Requires:       systemd
Requires(pre):  shadow-utils
AutoReqProv:    no

%description
PreySense controls supported Acer Predator PHN16S-71 hardware using a native Qt
interface and a DKMS bridge. Run preysense-setup as the desktop user after RPM
installation to grant hardware access and configure the per-user DTS backend.
No firmware, NVIDIA driver or proprietary DTS files are bundled.

%prep
%setup -q

%build

%install
install -d %{buildroot}/opt/preysense/linux/assets %{buildroot}/opt/preysense/linux/assets/Resources
install -m 644 linux/*.py %{buildroot}/opt/preysense/linux/
install -m 644 linux/assets/*.svg linux/assets/*.json %{buildroot}/opt/preysense/linux/assets/
cp -a linux/kwin linux/audio_backend %{buildroot}/opt/preysense/linux/
install -m 644 linux/assets/Resources/*.png linux/assets/Resources/Font.otf %{buildroot}/opt/preysense/linux/assets/Resources/
install -m 644 linux/assets/appicon.svg %{buildroot}/opt/preysense/linux/assets/
install -m 755 linux/hardware-permissions.sh %{buildroot}/opt/preysense/hardware-permissions.sh
install -m 755 linux/sign-driver.sh %{buildroot}/opt/preysense/linux/sign-driver.sh
install -d %{buildroot}/opt/preysense/docs/linux %{buildroot}/opt/preysense/licenses
install -m 644 docs/linux/*.md %{buildroot}/opt/preysense/docs/linux/
install -m 644 LICENSE %{buildroot}/opt/preysense/licenses/MIT
install -m 644 linux/kernel/COPYING %{buildroot}/opt/preysense/licenses/GPL-2.0
install -d %{buildroot}/usr/src/preysense-2.5.0
install -m 644 linux/kernel/preysense.c linux/kernel/Makefile linux/kernel/dkms.conf linux/kernel/COPYING %{buildroot}/usr/src/preysense-2.5.0/
install -D -m 755 linux/packaging/rpm/preysense %{buildroot}/usr/bin/preysense
install -D -m 755 linux/packaging/rpm/preysense-setup %{buildroot}/usr/bin/preysense-setup
install -D -m 644 linux/packaging/rpm/preysense.desktop %{buildroot}/usr/share/applications/preysense.desktop
install -D -m 644 linux/packaging/rpm/preysense-hardware.service %{buildroot}/usr/lib/systemd/system/preysense-hardware.service
install -D -m 644 linux/packaging/rpm/70-preysense.rules %{buildroot}/usr/lib/udev/rules.d/70-preysense.rules
install -D -m 644 linux/packaging/rpm/90-preysense-keyboard.hwdb %{buildroot}/usr/lib/udev/hwdb.d/90-preysense-keyboard.hwdb

%pre
getent group preysense >/dev/null || /usr/sbin/groupadd -r preysense

%post
systemctl daemon-reload || :
if ! dkms status -m preysense -v 2.5.0 2>/dev/null | grep -q .; then
    dkms add -m preysense -v 2.5.0 || echo 'PreySense DKMS registration failed; inspect dkms status.' >&2
fi
if ! dkms build -m preysense -v 2.5.0 -k "$(uname -r)" --force; then
    echo 'PreySense driver build/signing failed. Check running-kernel headers and Secure Boot signing.' >&2
elif ! dkms install -m preysense -v 2.5.0 -k "$(uname -r)" --force; then
    echo 'PreySense driver installation failed. Run dkms status for details.' >&2
fi
python3 -I /opt/preysense/linux/keymap.py save || :
systemd-hwdb update || :
udevadm control --reload-rules || :
echo 'Run preysense-setup as the desktop user to finish hardware access and DTS setup.'

%preun
if [ "$1" -eq 0 ]; then
    systemctl disable --now preysense-hardware.service || :
    python3 -I /opt/preysense/linux/keymap.py restore || :
    python3 -I /opt/preysense/linux/rpm_configure.py --remove || :
    dkms remove -m preysense -v 2.5.0 --all || :
fi

%postun
systemctl daemon-reload || :
systemd-hwdb update || :
udevadm control --reload-rules || :
udevadm trigger --subsystem-match=input || :
udevadm trigger --subsystem-match=hidraw || :

%files
/opt/preysense
/usr/src/preysense-2.5.0
/usr/bin/preysense
/usr/bin/preysense-setup
/usr/share/applications/preysense.desktop
/usr/lib/systemd/system/preysense-hardware.service
/usr/lib/udev/rules.d/70-preysense.rules
/usr/lib/udev/hwdb.d/90-preysense-keyboard.hwdb

%changelog
* Fri Nov 06 2026 PreySense developers - 1.0.0-1
- Initial Fedora RPM with DKMS source and explicit per-user DTS setup.
