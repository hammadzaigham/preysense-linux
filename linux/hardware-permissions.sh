#!/bin/sh
# Called only by the root-owned systemd unit with the install user's group.
set -eu
group="$1"
for name in profile fan_mode fan_duty battery_limit boot_sound led_timeout usb_charging gpu_mux; do
    chgrp "$group" "/sys/devices/platform/preysense/$name"
done
for domain in /sys/class/powercap/intel-rapl:0 /sys/class/powercap/intel-rapl-mmio:0; do
    [ -r "$domain/name" ] || continue
    [ "$(cat "$domain/name")" = package-0 ] || continue
    for name in constraint_0_power_limit_uw constraint_1_power_limit_uw constraint_0_time_window_us; do
        [ -f "$domain/$name" ] || continue
        chgrp "$group" "$domain/$name"
        chmod g+w "$domain/$name"
    done
    # CPU package power is read from an energy delta; grant read only, never writes.
    if [ -f "$domain/energy_uj" ]; then
        chgrp "$group" "$domain/energy_uj"
        chmod g+r "$domain/energy_uj"
    fi
done

boost=/sys/devices/system/cpu/intel_pstate/no_turbo
if [ -f "$boost" ]; then
 chgrp "$group" "$boost"
 chmod g+w "$boost"
fi
