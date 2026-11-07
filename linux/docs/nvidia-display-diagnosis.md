# NVIDIA-only panel diagnosis — 2026-11-06

The failed boot 567215939dce47cc9b0f1a2d624a0901 loaded NVIDIA 615.71.09,
but its DRM device reported no CRTC sizes and the login compositor had no outputs.
Intel reported failure retrieving eDP link information (expected possibility when
hardware MUX routes the panel to NVIDIA). Current working Hybrid boot
99ce712110d840ceb3535936333bb55f also logs NVIDIA DP-0 EDID read warnings.
Those warnings do not alone establish the cause of the discrete-only failure.

The installed override is 512 bytes with all four block checksums valid. This
checks integrity only, not panel compatibility or NVIDIA timing acceptance.

Official NVIDIA 615.71.09 kernel-open/nvidia-drm/nvidia-drm-connector.c supports
DRM EDID overrides through drm_edid_override_connector_update, passing the blob
to NVKMS. Do not claim drm.edid_firmware is universally ignored by this driver.

An optional BLS boot entry titled `PreySense - NVIDIA display test (stock EDID)`
was cloned from the current kernel entry. It removes drm.edid_firmware only for
that boot and enables drm.debug=0x1e/log_buf_len=4M. The normal entry, default
selection, firmware file, MUX setting and current display remain unchanged.
No reboot or NVIDIA-only test was performed by this investigation.

To isolate the override, select NVIDIA-only using the existing firmware control,
then select the stock-EDID diagnostic entry in GRUB at reboot. Record whether the
panel works. If it fails, restore Hybrid/Optimus through firmware setup and boot
the normal Fedora entry. Check the test boot kernel log and compositor output
messages. If stock works, compare EDID timing acceptance before changing the
global override. If it fails too, investigate panel detection, link training and
MUX/firmware interaction before attributing the failure to EDID timing data.

NVIDIA also has a private config_file override parser in
src/nvidia-modeset/src/nvkms-conf.c, using e.g.
`override.[0000:01:00.0].DP-0 = /lib/firmware/edid/edid-phn16s.bin`.
It force-connects the named NVIDIA display; do not globally enable it in Hybrid,
as that could create an output on the disconnected side of the MUX. It has NOT
been installed or tested. DRM connector names eDP-1/eDP-2 are not the names used
by this parser.

## Stock-EDID boot result

Boot abbdb0ba58954f398d01c873cfcdbb2e successfully runs firmware MUX 2
(NVIDIA-only) without drm.edid_firmware. NVIDIA card2-eDP-1 is connected
and enabled with a 256-byte original EDID; vendor is 0x10de. Atomic
commits drive the active panel. This isolates the custom EDID path as the
leading cause of earlier NVIDIA-only failure; checksums alone were not
sufficient validation. Connector numbering changes: NVIDIA is eDP-1 in
discrete mode, versus eDP-2 in Hybrid. Normal boot parameters still contain
the custom override, so the diagnostic boot result is not a permanent fix.

## Intel-only restriction installed

Removed unconditional drm.edid_firmware from all BLS entries and future-kernel
command-line sources. Added dracut module 91preysense-edid: cmdline priority01
checks PCI boot_vga vendor. Only Intel boot ownership enables the eDP-1 override;
NVIDIA/unknown ownership leaves stock EDID. The stock diagnostic entry explicitly
sets rd.preysense.edid=0. Current kernel initramfs rebuilt successfully. Module
persists for future kernel builds. Tests cover Intel/NVIDIA/unknown ownership;
next Hybrid boot is still required to verify automatic selection on real hardware.
Configuration backups are in /var/lib/preysense/edid-backup-1794019381.
Refresh-enabler project installer updated to preserve this policy on reinstall.
