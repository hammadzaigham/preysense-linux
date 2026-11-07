#!/usr/bin/env bash
# Desktop-user one-command Fedora setup. No unrelated weak dependencies.
set -euo pipefail
src="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-}"
if [[ $mode == --dependencies || $mode == --check ]]; then
    [[ -f /etc/fedora-release ]] || { echo 'Automatic dependencies currently support Fedora. See docs/linux/installation.md for manual distribution setup.' >&2; exit 1; }
    packages=(python3 python3-pyside6 gcc make dkms "kernel-devel-$(uname -r)" kscreen libkscreen kf6-kpackage mokutil pipewire pipewire-pulseaudio wireplumber)
    missing=()
    for package in "${packages[@]}"; do rpm -q "$package" >/dev/null 2>&1 || missing+=("$package"); done
    if [[ $mode == --check ]]; then
        printf 'Missing required packages: %s\n' "${missing[*]:-none}"
        exit 0
    fi
    [[ $EUID == 0 ]] || exec sudo "$0" --dependencies
    if ((${#missing[@]})); then dnf install -y --setopt=install_weak_deps=False "${missing[@]}"; fi
    exit 0
fi
[[ $EUID != 0 ]] || { echo 'Run ./linux/setup.sh as the desktop user; it requests sudo only for system installation.' >&2; exit 1; }
[[ $(cat /sys/class/dmi/id/product_name) == 'Predator PHN16S-71' ]] || { echo 'This hardware backend supports Predator PHN16S-71 only.' >&2; exit 1; }
sudo "$src/setup.sh" --dependencies
PREYSENSE_SETUP_DONE=1 "$src/install.sh"
python3 "$src/setup_audio.py"
if [[ -x "$src/sign-driver.sh" ]]; then
    echo 'Checking kernel module signing and Secure Boot status...'
    sudo "$src/sign-driver.sh" || echo 'Kernel module signing helper exited with an error. Review output above.' >&2
fi
echo 'PreySense and the per-user DTS backend are installed. Launch preysense.'
