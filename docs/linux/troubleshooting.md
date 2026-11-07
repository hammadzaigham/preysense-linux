# Troubleshooting and recovery

## Hardware controls are unavailable

Check the model and matching kernel build:

```sh
cat /sys/class/dmi/id/product_name
uname -r
systemctl status preysense-hardware.service
ls /sys/devices/platform/preysense
```

After a kernel upgrade, rerun the installer from the desktop account. Running the
GUI as root is not the fix for a missing bridge. Unsupported models are deliberately
rejected. A firmware error or readback mismatch remains an error, not a successful setting.

## Predator or Turbo does nothing

PreySense must be running, normally in the tray. Enable its login entry if the
buttons should work after login. Check `predator_events` before/after a physical
press and check that the matching 1025:174B hidraw node has the scoped read permission.
Do not remap unrelated scan codes or grant every input device access as a workaround.
The tested software path uses injected events; a physical report may still require
model-specific adjustment. The Turbo key cycles Eco, Quiet, Balanced, Performance and Turbo; firmware may reject unsupported requests.

## Custom fan control stops

An eight-second missed heartbeat deliberately gives ownership back to firmware.
Missing CPU temperature and failed firmware writes also end custom control. Look
at Diagnostics/current sensor availability and the displayed error. Zero RPM can
be a valid stopped fan; GPU temperature zero is treated as unavailable. Custom control follows the saved curve without a separate emergency override.

## Lighting stops in the tray or never times out

Hardware effects do not need a background frame loop; software effects do. Software
mode suppresses the EC's timeout while active, then uses the aggregate keyboard-idle
sensor. Stopping should restore the configured0–120second setting;0 disables timeout. If a process was
killed during an effect, explicitly choose the desired timeout after restarting.
Changing the Logo manually disables software logo synchronization for that session.

## GPU modes and reboot-dependent tests

Consult the GPU-mode notes. A firmware boot-setting readback is not
proof the live panel switched. NVIDIA module installation/build is not proof the
currently running nouveau session switched drivers. Do not hot-unbind the desktop
GPU or reboot another active development task just to remove a pending status.

## NVIDIA driver and hybrid rendering verified after restart

Post-restart checks on NVIDIA 615.71.09 confirmed `nvidia` bound to the RTX 5070
Ti, matching userspace/kernel versions and successful NVIDIA OpenGL rendering
under KDE Wayland. Default `glxinfo -B` used Intel; both explicit PRIME variables
and `switcherooctl launch -g 1 glxinfo -B` used the RTX 5070 Ti. `Disp.A Off` in
`nvidia-smi` means NVIDIA is not driving an active display; it does not mean the
driver or render offload is broken.

Use the existing KDE Wayland session for hybrid graphics. The standard path is
per-app PRIME render offload, independent of Advanced Optimus or display-mux
switching. `switcherooctl list` currently identifies Intel as device 0 and NVIDIA
as device 1; recheck IDs if hardware changes. Launch an app with:

```sh
switcherooctl launch -g 1 application
```

KDE Menu Editor also offers Advanced → Run using dedicated graphics card.
For Steam game launch options:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

See [KDE's multi-GPU guide](https://linux.kde.org/docs/multi-gpu/) and
[NVIDIA PRIME Render Offload](https://download.nvidia.com/XFree86/Linux-x86_64/615.71.09/README/primerenderoffload.html).
Firmware dGPU Only remains a separate reboot-dependent option for NVIDIA-driven
panel output. It is not necessary to run a game on NVIDIA.

The experimental Xfce session failed to provide a usable desktop. Its session
log reports missing `xfsettingsd`, a competing compositor, and desktop-portal
failures. Xorg initialized NVIDIA and later exited successfully; the log does not
establish a fatal NVIDIA driver failure. The minimal Xfce installation was
incomplete; no further Xfce packages or desktop changes were applied during this
check because X11/Advanced Optimus is no longer required.
