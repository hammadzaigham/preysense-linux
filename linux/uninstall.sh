#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || exec sudo "$0" "$@"
python3 -I "$(dirname -- "$0")/service_lifecycle.py" --remove
systemctl disable --now preysense-hardware.service || true
rm -f /etc/systemd/system/preysense-hardware.service /etc/udev/rules.d/70-preysense.rules /etc/udev/hwdb.d/90-preysense-keyboard.hwdb /usr/local/bin/preysense /usr/local/bin/preysense-fps /usr/local/bin/preysensed /usr/share/applications/preysense.desktop
if command -v dkms >/dev/null 2>&1; then
    dkms remove -m preysense -v 2.5.0 --all >/dev/null 2>&1 || true
    rm -rf /usr/src/preysense-2.5.0
fi
# Remove installed preysense kernel modules including compressed variants across kernel directories
rm -f /lib/modules/*/extra/preysense.ko* /lib/modules/*/updates/dkms/preysense.ko* /lib/modules/*/updates/preysense.ko*
for domain in /sys/class/powercap/intel-rapl:0 /sys/class/powercap/intel-rapl-mmio:0; do
 [ -d "$domain" ] || continue
 for name in constraint_0_power_limit_uw constraint_1_power_limit_uw constraint_0_time_window_us; do
  [[ ! -f "$domain/$name" ]] || { chgrp root "$domain/$name"; chmod g-w "$domain/$name"; }
 done
 if [[ -f "$domain/energy_uj" ]]; then chgrp root "$domain/energy_uj"; chmod g-r "$domain/energy_uj"; fi
done
if [[ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then
 chgrp root /sys/devices/system/cpu/intel_pstate/no_turbo
 chmod g-w /sys/devices/system/cpu/intel_pstate/no_turbo
fi

rm -rf /opt/preysense
systemctl daemon-reload
systemd-hwdb update
udevadm trigger --subsystem-match=input
udevadm settle
if [[ -f /var/lib/preysense/keymap.json ]]; then python3 -I "$(dirname -- "$0")/keymap.py" restore; fi
rm -rf /var/lib/preysense
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw
depmod -a
if [[ -n ${SUDO_USER:-} ]]; then
 user_home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
 rm -f "$user_home/.config/autostart/preysense.desktop"
 rm -rf "$user_home/.config/PreySense"
 rm -rf "$user_home/.local/share/kwin/effects/preysense-instant"
 rm -f "$user_home/.local/share/applications/preysense.desktop"
fi
printf 'PreySense system files and user preferences removed.\n'
