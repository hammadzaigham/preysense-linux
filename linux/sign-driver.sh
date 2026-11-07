#!/usr/bin/env bash
# Sign through DKMS without replacing keys or disabling Secure Boot.
set -euo pipefail
MODULE=preysense
VERSION=2.5.0
KERNEL="$(uname -r)"
KEY=/var/lib/dkms/mok.key
CERT=/var/lib/dkms/mok.pub
CUSTOM=0
KEY_SET=0
CERT_SET=0
usage() {
    cat <<'HELP'
Usage: sudo ./linux/sign-driver.sh [--kernel VERSION] [--key FILE --cert FILE]
Requires an installed PreySense DKMS source tree and matching kernel headers.
Custom paths must match the existing DKMS framework signing configuration.
Requests MOK enrollment if necessary; never reboots or unloads drivers itself.
HELP
}
while (($#)); do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --kernel|--key|--cert)
            (($# >= 2)) && [[ -n "$2" && "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 1; }
            case "$1" in
                --kernel) KERNEL=$2 ;;
                --key) KEY=$2; KEY_SET=1; CUSTOM=1 ;;
                --cert) CERT=$2; CERT_SET=1; CUSTOM=1 ;;
            esac
            shift 2 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
done
[[ "$KERNEL" != */* ]] || { echo 'Invalid kernel version.' >&2; exit 1; }
((KEY_SET == CERT_SET)) || { echo 'Supply both --key and --cert.' >&2; exit 1; }
((EUID == 0)) || { echo 'Run with sudo.' >&2; exit 1; }
for cmd in dkms mokutil modinfo depmod openssl; do
    command -v "$cmd" >/dev/null || { echo "Missing prerequisite: $cmd" >&2; exit 1; }
done
[[ -d "/usr/src/${MODULE}-${VERSION}" ]] || {
    echo "DKMS source /usr/src/${MODULE}-${VERSION} not found. Install PreySense first." >&2; exit 1;
}
[[ -d "/lib/modules/${KERNEL}/build" ]] || {
    echo "Kernel build files missing for ${KERNEL}. Install matching kernel-devel." >&2; exit 1;
}
# Evaluate the same root-owned framework configuration DKMS uses, in isolation.
# Checking the effective values also catches indirect assignments and includes.
configured="$(bash -c '
    kernelver=$1
    mok_signing_key=/var/lib/dkms/mok.key
    mok_certificate=/var/lib/dkms/mok.pub
    for file in /etc/dkms/framework.conf /etc/dkms/framework.conf.d/*.conf; do
        if [[ -f "$file" ]]; then source "$file" >&2 || exit 1; fi
    done
    printf "%s\n%s\n" "$mok_signing_key" "$mok_certificate"
' bash "$KERNEL")"
mapfile -t configured_paths <<< "$configured"
((${#configured_paths[@]} == 2)) || { echo 'Cannot resolve DKMS signing paths.' >&2; exit 1; }
if [[ "$KEY" != "${configured_paths[0]}" || "$CERT" != "${configured_paths[1]}" ]]; then
    echo 'Selected key/certificate must match the existing DKMS configuration.' >&2
    printf 'Rerun with --key %q --cert %q\n' "${configured_paths[0]}" "${configured_paths[1]}" >&2
    exit 1
fi
if [[ ! -f "$KEY" || ! -f "$CERT" ]]; then
    if [[ -e "$KEY" || -e "$CERT" ]]; then
        echo 'Only one signing file exists; refusing to replace either.' >&2; exit 1;
    fi
    if ((CUSTOM)); then
        echo 'Specified signing files not found; refusing to create replacements.' >&2; exit 1;
    fi
    echo 'Requesting DKMS to generate its default signing key.'
    dkms generate_mok
fi
[[ -f "$KEY" && -f "$CERT" ]] || { echo 'DKMS signing files unavailable.' >&2; exit 1; }
keyhash="$(openssl pkey -in "$KEY" -pubout -outform DER | openssl dgst -sha256)"
certhash="$(openssl x509 -inform DER -in "$CERT" -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256)"
[[ "$keyhash" == "$certhash" ]] || { echo 'Private key and certificate do not match.' >&2; exit 1; }
sb_state="$(mokutil --sb-state 2>&1 || true)"
echo "$sb_state"
if [[ "$sb_state" == *'SecureBoot enabled'* ]]; then
    if ! mokutil --test-key "$CERT" >/dev/null 2>&1; then
        echo 'Requesting certificate enrollment. Set a one-time password when prompted.'
        mokutil --import "$CERT"
        cat <<'STEPS'
Reboot, then in the blue MOK Manager:
  Enroll MOK -> Continue -> Yes -> enter your one-time password -> Reboot
After returning to Fedora, rerun this script to build/install the driver.
Secure Boot validation is not disabled by this script.
STEPS
        exit 0
    fi
    echo 'Signing certificate is already enrolled.'
elif [[ "$sb_state" == *'SecureBoot disabled'* || "$sb_state" == *"EFI variables are not supported"* ]]; then
    echo 'Secure Boot is not enabled; signing will proceed without enrollment.'
else
    echo 'Cannot determine Secure Boot state; refusing to assume enrollment is unnecessary.' >&2; exit 1
fi
# DKMS signs before compression, using the configured pair verified above.
echo "Building ${MODULE}/${VERSION} for ${KERNEL} with DKMS..."
dkms build -m "$MODULE" -v "$VERSION" -k "$KERNEL" --force
dkms install -m "$MODULE" -v "$VERSION" -k "$KERNEL" --force
depmod -a "$KERNEL"
signer="$(modinfo -k "$KERNEL" -F signer "$MODULE" 2>/dev/null || true)"
[[ -n "$signer" ]] || { echo 'ERROR: Installed module has no signer. Check DKMS signing configuration.' >&2; exit 1; }
printf 'Installed module signer: %s\n' "$signer"
echo 'Reboot before loading the rebuilt module if the old one is currently loaded.'
