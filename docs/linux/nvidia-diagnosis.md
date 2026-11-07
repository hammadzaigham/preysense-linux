# NVIDIA driver and Secure Boot

PreySense reads NVIDIA telemetry through the NVIDIA driver. An installed driver
package does not prove that its kernel module can load. If the app reports an
unavailable driver, inspect these separately:

```sh
uname -r
modinfo -F version nvidia
modinfo -F signer nvidia
mokutil --sb-state
lspci -nnk -d 10de:
nvidia-smi
```

## Diagnosis on this development laptop (6 November 2026)

The current Fedora kernel is `7.2.15-300.fc45.x86_64`. NVIDIA driver `615.71.09`
and its matching kernel module were already installed. Secure Boot was enabled,
but the NVIDIA module was unsigned. Loading it failed with **Key was rejected by
service**. Nouveau was bound to the RTX 5070 Ti Laptop GPU instead. Installing
more driver packages would not address this signature problem.

The akmods signing certificate was not enrolled. An existing certificate at
`/etc/pki/vmd/MOK.der` was already enrolled and signs the working PreySense
hardware module. Protected copies of this existing key pair were placed in
`/etc/pki/akmods/{private,certs}/preysense-enrolled.{priv,der}` and the standard
akmods `private_key.priv` / `public_key.der` links were updated to them. Original
key files were retained; their previous link targets are recorded under
`/etc/pki/akmods/previous-*-key-link.txt`. No private keys are stored in this
repository. Akmods uses those standard paths when building future kernels.

The NVIDIA module was rebuilt successfully and now reports signer
`Predator VMD local module signing`. The certificate enrollment check passes.
Persistent settings in `/etc/modprobe.d/preysense-nvidia.conf` blacklist Nouveau
and nova_core. `/etc/dracut.conf.d/90-preysense-nvidia.conf` excludes these drivers
and explicitly includes NVIDIA modules in future boot images. The current boot
image was regenerated. No packages were added. To undo the boot-driver policy,
remove those two configuration files and regenerate the boot image with dracut;
this does not remove either installed driver.

## Safe activation

A live session using Nouveau must be restarted to change drivers. Do not unload
or unbind the active display driver from the running desktop. After a normal
reboot, verify:

```sh
modinfo -F signer nvidia
nvidia-smi
lspci -nnk -d 10de:
```

The graphics device should report `Kernel driver in use: nvidia`, and
`nvidia-smi` should list the GPU. Until then, driver-dependent power readings and
controls can remain unavailable. A successful package build or a signer field
alone does not verify runtime operation.

## Future kernel updates

Fedora akmods builds modules for new kernels. With Secure Boot enabled, its
signing certificate must remain enrolled. Diagnose a later failure with:

```sh
sudo mokutil --test-key /etc/pki/akmods/certs/public_key.der
sudo akmods --force --rebuild --akmod nvidia --kernels "$(uname -r)"
sudo journalctl -k -b
```

Use the installed `/usr/share/doc/akmods/README.secureboot` for enrollment if a
machine has no existing trusted key. Enrollment requires physical interaction in
the firmware MOK screen; PreySense never disables Secure Boot automatically.
