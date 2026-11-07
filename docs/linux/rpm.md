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

## Manual RPM signing and verification

RPM signing identifies the package publisher using an OpenPGP key. Secure Boot
uses a separate kernel-module signing key: signing the RPM does not enroll a MOK
or make the PreySense driver trusted by firmware.

The attached development RPMs are currently unsigned. Normally the maintainer
signs packages once and users import the public key. Signing a downloaded RPM
with your own key only records your own approval; it does not prove that the
original download came from the maintainer.

### Maintainer: create a signing key

Install only the signing tools if missing:

```sh
sudo dnf install rpm-sign gnupg2
gpg --full-generate-key
gpg --list-secret-keys --keyid-format long
```

Choose a signing-capable key (for example RSA 3072 or 4096), protect it with a
passphrase, and keep the private key and its backup off GitHub. Copy the full
fingerprint shown for your signing key into the variable below. Do not use the
Secure Boot MOK key for this.

### Maintainer: sign and export the public key

Run as your normal user, in the directory containing the RPMs. Replace the
placeholder fingerprint before running:

```sh
PREYSENSE_SIGNING_KEY='REPLACE_WITH_FULL_OPENPGP_FINGERPRINT'
rpmsign --define '_openpgp_sign gpg' \
  --define "_openpgp_sign_id ${PREYSENSE_SIGNING_KEY}" \
  --addsign preysense-1.0.0-1.fc45.x86_64.rpm
rpmsign --define '_openpgp_sign gpg' \
  --define "_openpgp_sign_id ${PREYSENSE_SIGNING_KEY}" \
  --addsign preysense-1.0.0-1.fc45.src.rpm
gpg --armor --export "$PREYSENSE_SIGNING_KEY" > RPM-GPG-KEY-PreySense.asc
gpg --show-keys --with-fingerprint RPM-GPG-KEY-PreySense.asc
sha256sum preysense-1.0.0-1.fc45.x86_64.rpm \
  preysense-1.0.0-1.fc45.src.rpm > SHA256SUMS
```

Signing changes the RPM bytes, so regenerate checksums afterward. Publish the
signed RPMs, public key, new checksums and full public-key fingerprint together.
Never publish the private key. The public key is not currently supplied with the
unsigned v1.0.0 release; the following verification steps apply after a signed
release is published, or to packages you signed yourself.

### User: trust and verify a signed package

Obtain the public key from the maintainer, compare its full fingerprint with a
trusted publication from the maintainer, then import it:

```sh
gpg --show-keys --with-fingerprint RPM-GPG-KEY-PreySense.asc
sudo rpm --import ./RPM-GPG-KEY-PreySense.asc
rpm -Kv ./preysense-1.0.0-1.fc45.x86_64.rpm
sudo dnf --setopt=localpkg_gpgcheck=1 install ./preysense-1.0.0-1.fc45.x86_64.rpm
```

Check for a valid OpenPGP signature as well as valid digests. `NOKEY` means the
signing key has not been trusted locally; missing signatures mean the package
is unsigned. Do not treat SHA256 digests alone as publisher authentication.

Reference: [RPM's official rpmsign manual](https://rpm.org/docs/6.0.x/man/rpmsign.1).
