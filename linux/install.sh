#!/usr/bin/env bash
# Core installation; setup.sh supplies missing dependencies and per-user DTS setup.
set -euo pipefail
src="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
user="${SUDO_USER:-$(id -un)}"
if [[ $EUID != 0 && ${PREYSENSE_SETUP_DONE:-0} != 1 ]]; then exec "$src/setup.sh"; fi
if [[ $EUID != 0 ]]; then
    python3 -c 'from PySide6 import QtWidgets' || { echo 'PySide6 is required. Install your distribution python3-pyside6 package.'; exit 1; }
    make -C "$src/kernel"
    exec sudo "$src/install.sh" "$user"
fi
user="${1:-$user}"
[[ $user != root ]] || { echo 'Run as the desktop user with sudo, or pass the desktop username.'; exit 1; }
[[ $(cat /sys/class/dmi/id/product_name) == 'Predator PHN16S-71' ]] || { echo 'The hardware bridge currently supports Predator PHN16S-71 only.'; exit 1; }
group="$(id -gn "$user")"
[[ $group =~ ^[a-zA-Z_][a-zA-Z0-9_-]*\$?$ ]] || exit 1
[[ -f "$src/kernel/preysense.ko" ]] || { echo 'Build linux/kernel before installing'; exit 1; }
install -d /opt/preysense/linux/assets /opt/preysense/PreySense.Frontend/Resources /opt/preysense/licenses
install -m 644 "$src/"*.py /opt/preysense/linux/
install -d /opt/preysense/linux/audio_backend
install -m 644 "$src/audio_backend/"* /opt/preysense/linux/audio_backend/
install -D -m 644 "$src/kwin/preysense-instant/metadata.json" /opt/preysense/linux/kwin/preysense-instant/metadata.json
install -D -m 644 "$src/kwin/preysense-instant/contents/code/main.js" /opt/preysense/linux/kwin/preysense-instant/contents/code/main.js
install -d /opt/preysense/docs/linux
install -m 644 "$src/../docs/linux/"*.md /opt/preysense/docs/linux/
install -m 644 "$src/README.md" "$src/REMAINING.md" /opt/preysense/linux/
install -m 644 "$src/assets/"*.svg "$src/assets/"*.json /opt/preysense/linux/assets/
install -m 644 "$src/kernel/COPYING" /opt/preysense/licenses/GPL-2.0
install -m 644 "$src/../LICENSE" /opt/preysense/licenses/MIT
install -m 755 "$src/hardware-permissions.sh" /opt/preysense/hardware-permissions.sh
install -m 644 "$src/../PreySense.Frontend/Resources/"*.png "$src/../PreySense.Frontend/Resources/Font.otf" /opt/preysense/PreySense.Frontend/Resources/
install -m 644 "$src/../PreySense.Frontend/appicon.svg" /opt/preysense/PreySense.Frontend/

# Check Secure Boot state
secure_boot_active=0
if command -v mokutil >/dev/null 2>&1; then
    if mokutil --sb-state 2>/dev/null | grep -qi "SecureBoot enabled"; then
        secure_boot_active=1
    fi
fi

# Set up DKMS for automatic module rebuilds on kernel updates if dkms is available
if command -v dkms >/dev/null 2>&1; then
    dkms_ver="2.5.0"
    dkms_src="/usr/src/preysense-$dkms_ver"
    target_kver="$(uname -r)"

    # Validate compilation in a temporary clean staging directory before touching active DKMS
    echo "Validating PreySense kernel module compilation for $target_kver..."
    staging_build_dir="$(mktemp -d -t preysense-dkms-stage-XXXXXX)"
    install -m 644 "$src/kernel/preysense.c" "$src/kernel/Makefile" "$src/kernel/dkms.conf" "$src/kernel/COPYING" "$staging_build_dir/"

    if ! make -C "/lib/modules/$target_kver/build" M="$staging_build_dir" modules > /dev/null; then
        echo "ERROR: Kernel module staging compilation failed against $target_kver headers." >&2
        rm -rf "$staging_build_dir"
        exit 1
    fi
    rm -rf "$staging_build_dir"

    # Backup existing DKMS source tree if present
    backup_src=""
    if [[ -d "$dkms_src" ]]; then
        backup_src="$(mktemp -d -t preysense-src-bak-XXXXXX)"
        cp -a "$dkms_src/." "$backup_src/"
    fi

    # Populate /usr/src/preysense-$dkms_ver with ONLY clean source files (no dirty build artifacts)
    rm -rf "$dkms_src"
    mkdir -p "$dkms_src"
    install -m 644 "$src/kernel/preysense.c" "$src/kernel/Makefile" "$src/kernel/dkms.conf" "$src/kernel/COPYING" "$dkms_src/"

    # Unregister existing version to allow clean registration of new source tree
    dkms remove -m preysense -v "$dkms_ver" --all >/dev/null 2>&1 || true

    if ! dkms add -m preysense -v "$dkms_ver"; then
        echo "ERROR: dkms add failed." >&2
        if [[ -n "$backup_src" && -d "$backup_src" ]]; then
            rm -rf "$dkms_src"
            mv "$backup_src" "$dkms_src"
            dkms add -m preysense -v "$dkms_ver" >/dev/null 2>&1 || true
            dkms install -m preysense -v "$dkms_ver" -k "$target_kver" --force >/dev/null 2>&1 || true
        fi
        exit 1
    fi

    if ! dkms build -m preysense -v "$dkms_ver" -k "$target_kver"; then
        echo "ERROR: dkms build failed for kernel $target_kver." >&2
        dkms remove -m preysense -v "$dkms_ver" --all >/dev/null 2>&1 || true
        if [[ -n "$backup_src" && -d "$backup_src" ]]; then
            rm -rf "$dkms_src"
            mv "$backup_src" "$dkms_src"
            dkms add -m preysense -v "$dkms_ver" >/dev/null 2>&1 || true
            dkms install -m preysense -v "$dkms_ver" -k "$target_kver" --force >/dev/null 2>&1 || true
        fi
        exit 1
    fi

    if ! dkms install -m preysense -v "$dkms_ver" -k "$target_kver" --force; then
        echo "ERROR: dkms install failed for kernel $target_kver." >&2
        dkms remove -m preysense -v "$dkms_ver" --all >/dev/null 2>&1 || true
        if [[ -n "$backup_src" && -d "$backup_src" ]]; then
            rm -rf "$dkms_src"
            mv "$backup_src" "$dkms_src"
            dkms add -m preysense -v "$dkms_ver" >/dev/null 2>&1 || true
            dkms install -m preysense -v "$dkms_ver" -k "$target_kver" --force >/dev/null 2>&1 || true
        fi
        exit 1
    fi

    # Clean up source backup on success
    if [[ -n "$backup_src" && -d "$backup_src" ]]; then
        rm -rf "$backup_src"
    fi
else
    if [[ $secure_boot_active -eq 1 ]]; then
        echo "ERROR: Secure Boot is enabled but DKMS is not available to build and sign kernel modules." >&2
        echo "Direct installation of unsigned preysense.ko is rejected under Secure Boot." >&2
        exit 1
    fi
    install -D -m 644 "$src/kernel/preysense.ko" "/lib/modules/$(uname -r)/extra/preysense.ko"
    depmod -a
fi

cat > /usr/local/bin/preysense <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /opt/preysense/linux/preysense.py "$@"
EOF
chmod 755 /usr/local/bin/preysense

cat > /usr/share/applications/preysense.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=PreySense
GenericName=Acer Control Center
Comment=Control your Acer laptop
Keywords=acer;predator;preysense;prey;sense;
Exec=/usr/local/bin/preysense
Icon=/opt/preysense/PreySense.Frontend/appicon.svg
Categories=Settings;HardwareSettings;
Terminal=false
EOF
cat > /etc/udev/rules.d/70-preysense.rules <<EOF
SUBSYSTEM=="hidraw", KERNELS=="0018:0CF2:5130.*", GROUP="$group", MODE="0660"
SUBSYSTEM=="hidraw", KERNELS=="0018:1025:174B.*", GROUP="$group", MODE="0640"
EOF
python3 -I "$src/keymap.py" save
cat > /etc/udev/hwdb.d/90-preysense-keyboard.hwdb <<'EOF'
evdev:atkbd:dmi:*svnAcer:pnPredatorPHN16S-71:*
 KEYBOARD_KEY_75=prog3
 KEYBOARD_KEY_f5=prog3
EOF
systemd-hwdb update
udevadm trigger --subsystem-match=input
# No new groups or login required: access is limited to the install user's group.
cat > /etc/systemd/system/preysense-hardware.service <<EOF
[Unit]
Description=PreySense Acer hardware bridge
After=systemd-udevd.service
ConditionPathExists=/sys/class/dmi/id/product_name
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/modprobe preysense
ExecStartPost=/opt/preysense/hardware-permissions.sh $group
ExecStartPost=/usr/bin/python3 -I /opt/preysense/linux/memory_reader.py
RuntimeDirectory=preysense-memory
RuntimeDirectoryMode=0755
ExecStop=/sbin/modprobe -r preysense
[Install]
WantedBy=multi-user.target
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw
systemctl daemon-reload
systemctl enable preysense-hardware.service
systemctl restart preysense-hardware.service
printf '\nInstalled PreySense. Launch from the application menu or run: preysense\n'
printf 'Uninstall: sudo %s/uninstall.sh\n' "$src"

# The same hardware helper publishes configured RAM speed once at startup.
python3 -I /opt/preysense/linux/service_lifecycle.py "$user"
systemctl daemon-reload
systemctl enable preysense-hardware.service
