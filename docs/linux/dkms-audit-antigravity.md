# PreySense DKMS and Installer Hardening Audit

**Date**: 2026-11-06
**Auditor**: Installer and DKMS Hardening Agent (Antigravity)
**System Target**: Fedora 45 x86_64 (`7.2.15-300.fc45.x86_64`) on Acer Predator Helios Neo 16 (`PHN16S-71`)
**Security Status**: UEFI Secure Boot Enabled

---

## 1. Executive Summary

An audit of the existing installer (`linux/install.sh`), uninstaller (`linux/uninstall.sh`), and the previous draft patch (`agent_bridge/dkms-fixes.patch`) identified critical reliability and security issues under Linux environments with Secure Boot:

1. **Swallowed Failures & Insecure Fallbacks**: The previous installer pipeline ignored DKMS failures (`dkms add ... || true`, `dkms build ... || true`, `dkms install ... || true`). If DKMS compilation or signing failed under Secure Boot, falling back to an unsigned module copy into `/lib/modules/...` would cause kernel module loading to fail (`PKCS#7 signature missing / Key was rejected by service`).
2. **Premature Tree Destruction**: The prior draft patch removed the working, installed module registration (`dkms remove -m preysense -v 2.5.0 --all`) *before* compiling or validating the incoming source tree. If compilation failed (e.g., missing kernel headers, compiler error, syntax issue), the system was left with a broken driver and no fallback.
3. **Contaminated DKMS Staging Trees**: Previous scripts copied the entire `linux/kernel/*` directory into `/usr/src/preysense-2.5.0/`, polluting `/usr/src` with dirty host build artifacts (`.ko`, `.o`, `.mod`, `Module.symvers`, `.cmd` files).
4. **Key Security Compliance**: Fedora uses `/etc/dkms/framework.conf.d/vmd-signing.conf` referencing enrolled keys `/etc/pki/vmd/MOK.priv` and `/etc/pki/vmd/MOK.der` (enrolled fingerprint `77:0c:8d:13:...`, Subject `CN=Predator VMD local module signing`). Private keys must remain protected and never be printed, exposed, or overridden.
5. **Uninstall Incomplete Cleanup**: The uninstaller failed to remove compressed kernel modules (`.ko.xz` and `.ko.zst`), did not clean `/var/lib/preysense/`, failed to guard against non-existent powercap domains, and left stale configuration.

---

## 2. Hardened Architecture & Design

### 2.1 Build-in-Staging Pre-Validation
Before any change is made to the active DKMS registration or `/usr/src/preysense-2.5.0`, the new source is staged to a dedicated temporary directory (`mktemp -d -t preysense-dkms-stage-XXXXXX`). A preliminary build test executes against the running kernel headers:
```bash
make -C "/lib/modules/$target_kver/build" M="$staging_build_dir" modules
```
If this build test fails:
- Installation immediately aborts with exit code 1.
- No existing DKMS registration or source tree is touched.
- The known-good module remains active and intact.

### 2.2 Atomic DKMS Replacement with Backup & Rollback
When staging compilation succeeds:
1. Any existing `/usr/src/preysense-$dkms_ver` is backed up to a temporary backup directory (`cp -a`).
2. `/usr/src/preysense-$dkms_ver` is created fresh containing **only** clean source files:
   - `preysense.c`
   - `Makefile`
   - `dkms.conf`
   - `COPYING`
3. The existing DKMS registration is unregistered cleanly (`dkms remove -m preysense -v "$dkms_ver" --all`).
4. New source is registered (`dkms add`), built (`dkms build`), and installed (`dkms install --force`).
5. **Rollback Guard**: If `dkms add`, `dkms build`, or `dkms install` fails at any point:
   - The backup source tree is restored.
   - The previous known-good version is re-registered and re-installed.
   - The installer halts with a fatal error; it **never** silently succeeds.

### 2.3 Secure Boot Strict Enforcement
- Secure Boot state is verified via `mokutil --sb-state`.
- If Secure Boot is active and DKMS is unavailable or fails, direct installation of an unsigned `.ko` is strictly rejected.
- DKMS signing relies on `/etc/dkms/framework.conf.d/vmd-signing.conf` without exposing private keys.

### 2.4 Uninstaller Hardening (`uninstall.sh`)
- Scoped module cleanup matches all compression variants:
  `rm -f /lib/modules/*/extra/preysense.ko* /lib/modules/*/updates/dkms/preysense.ko* /lib/modules/*/updates/preysense.ko*`
  `rm -f /lib/modules/*/extra/preysense_acpi.ko /lib/modules/*/extra/preysense_acpi.ko.xz /lib/modules/*/extra/preysense_acpi.ko.zst`
- RAPL powercap domain loops check `[ -d "$domain" ]` before querying attributes, safely restoring root ownership and permissions (`constraint_*_power_limit_uw`, `constraint_0_time_window_us`, `energy_uj`).
- Keyboard keymap restoration is executed via `keymap.py restore`, followed by removal of `/var/lib/preysense`.
- Hardware services (`preysense-hardware.service`, `preysense-acpi.service`) and udev / hwdb rules are completely cleaned.

---

## 3. Verification & Validation Results

1. **Staging Build Harness**:
   - Clean source staging tested against kernel `7.2.15-300.fc45.x86_64` headers: PASS.
   - Invalid source failure detection and abort behavior: PASS.
2. **Rollback & Restore Harness**:
   - Simulated DKMS build failure triggering atomic backup restoration: PASS (known-good tree preserved).
3. **Secure Boot Check**:
   - `mokutil --sb-state` detected active Secure Boot (`SecureBoot enabled`). Direct unsigned copy rejected: PASS.
4. **Shell Syntax Validation**:
   - `bash -n linux/install.sh`: PASS.
   - `bash -n linux/uninstall.sh`: PASS.
5. **Patch Compatibility**:
   - `git apply --check /home/hammad/agent_bridge/dkms-fixes.patch`: PASS.
