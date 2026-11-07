# Kernel driver signing and Secure Boot

PreySense uses the `preysense` kernel module for Acer controls. When Secure Boot
validation is enabled, that module must be signed with a key trusted by your
kernel. This guide keeps validation enabled and uses DKMS to sign rebuilds.
The app version is 1.0.0; the internal driver/DKMS version is 2.5.0.

These steps are for Fedora booted through its normal shim bootloader. They do
not sign NVIDIA drivers and do not sign the RPM package. If Secure Boot is off,
key enrollment is normally unnecessary. If your current DKMS key is already
enrolled and the signed module loads, no additional key or enrollment is needed.

## Signing script

After installing PreySense, run from the source checkout:

```sh
sudo ./linux/sign-driver.sh
```

It checks prerequisites and the key/certificate pair, requests enrollment if
needed, then builds and installs the signed driver through DKMS. If enrollment
is requested, complete the MOK Manager steps after reboot and rerun the script.
It does not reboot, unload the active driver, change global DKMS settings, or
disable validation. Unknown Secure Boot state stops the script.

For an existing custom DKMS key, specify both configured paths:

```sh
sudo ./linux/sign-driver.sh --key /path/to/private.key --cert /path/to/public.der
```

These options verify the existing DKMS configuration; they do not override it.
`--kernel VERSION` targets another installed kernel with matching build files.
PKCS#11 keys are not supported by this file-based script. The manual steps below
are available if you prefer to perform each stage yourself.

## 1. Check your setup

```sh
mokutil --sb-state
dkms status
modinfo -F signer preysense
```

A signer name alone does not prove that its certificate is enrolled. Before
creating anything, inspect your DKMS configuration for existing key paths:

```sh
sudo rg '^[[:space:]]*(mok_signing_key|mok_certificate|sign_file)=' /etc/dkms/framework.conf /etc/dkms/framework.conf.d/
```

If `rg` is not installed, open those configuration files in a text editor instead.
A missing configuration directory is harmless. Do not replace an existing key:
it may also sign other DKMS drivers. The examples below use the upstream defaults
`/var/lib/dkms/mok.key` (private) and `/var/lib/dkms/mok.pub` (public DER certificate).
If your configuration overrides these paths, use its certificate path below.

## 2. Prepare the DKMS signing key

The PreySense installer installs DKMS and matching kernel build dependencies.
Install those prerequisites first if you have not run setup:

```sh
sudo dnf install dkms mokutil "kernel-devel-$(uname -r)" gcc make
sudo dkms generate_mok
```

DKMS generates a key/certificate when needed using its configured paths. Keep
both files in place for future kernel updates. Only the public certificate is
enrolled; never upload the private `.key` file. If you already have a configured
key/certificate pair, retain it rather than generating a replacement.

## 3. Enroll the public certificate once

For the default certificate path:

```sh
sudo mokutil --test-key /var/lib/dkms/mok.pub
```

If it is already enrolled, skip the import and reboot. Otherwise:

```sh
sudo mokutil --import /var/lib/dkms/mok.pub
```

Choose a temporary enrollment password when prompted, then reboot when ready.
At the blue MOK Manager screen, choose **Enroll MOK → Continue → Yes**, enter
that temporary password, then choose **Reboot**. Menu wording may vary slightly.
Choose enrollment, not a change to Secure Boot validation. This requires physical
access to the laptop; importing the certificate alone does not finish enrollment.

After boot:

```sh
sudo mokutil --test-key /var/lib/dkms/mok.pub
```

It should report that the key is enrolled.

## 4. Build and install the signed driver

Install PreySense first if its source is not registered with DKMS. Then, with
PreySense closed, rebuild for the running kernel:

```sh
sudo dkms build -m preysense -v 2.5.0 -k "$(uname -r)" --force
sudo dkms install -m preysense -v 2.5.0 -k "$(uname -r)" --force
sudo depmod -a
modinfo -F signer preysense
```

Check the DKMS build output: it prints the signing key and certificate used.
They must match the certificate you enrolled. Reboot to load the newly installed
driver, then start PreySense normally. To test module loading after that reboot:

```sh
sudo modprobe preysense
```

Do not manually append a signature to a compressed `.ko.xz` or `.ko.zst` file;
DKMS handles signing the built module before installation/compression.

## Kernel updates and troubleshooting

DKMS reuses its configured signing key when rebuilding for new kernels. With
matching kernel headers installed and the same certificate enrolled, normal
updates do not require enrolling a new key. Check `dkms status` after an update.

If loading reports `Key was rejected by service`, compare the DKMS signing
certificate path with the enrolled certificate and complete enrollment. If
building fails, check the DKMS build log and matching kernel headers. A successful
build does not mean the firmware enrollment was completed. Do not disable
validation to work around a missing enrollment.

References: [DKMS signing documentation](https://github.com/dkms-project/dkms/blob/main/README.md)
and [MOK management documentation](https://github.com/lcp/mokutil/blob/master/man/mokutil.1).
