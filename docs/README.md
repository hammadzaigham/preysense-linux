# PreySense technical documentation

Engineering notes for the PHN16S-71 control paths PreySense actually uses. Start with the [root README](../README.md) for product behavior; use this folder for registers, WMI payloads, and ACPI.

| Document | What it explains |
| :--- | :--- |
| [CPU power limits](cpu_power_limits_acpi.md) | Intel RAPL MMIO (`CPWR`), the 85 W PCCC/IPF clamp, RAPL Tau encoding, ERM4 factory CPU table, and `PreySenseControl` methods 3–4. |
| [GPU power limits](gpu_power_limits_nvpcf.md) | VBIOS vs ACPI NVPCF, ERM4 `MxCT`/`MxDB`, WMG3, and runtime TGP through PREYDEV methods 5–8. |
| [GPU switching](gpu_switching_and_dds.md) | NVIDIA Advanced Optimus (`nvcpl.dll`) and Acer BIOS mux. |
| [WMI and services](hardware_wmi_and_services.md) | `AcerGamingFunction`, fans, battery, USB charging, sensors, OEM debloater. Lighting is not on this bus. |
| [Keyboard and logo RGB](keyboard_rgb_ec.md) | ENEK5130 HID report `0xA4`, 4-zone keyboard, cover logo `0x83`, software engine, cover sync. |
| [Display and color](display_and_color.md) | Win32 refresh rate, LCD overdrive WMI, BlueLight Shield gamma ramps. |
| [DTS Custom Audio](dts_custom_audio.md) | Preset labels and the `dtscnt64.dll` controls behind Custom Audio. |
| [OpenCore ACPI](opencore_acpi_patching.md) | `SSDT-PREYDEV`, PCCC and E3DT patches, hidden `PREYSENSE` partition, BIOS enrollment. |
| [BIOS setup_var offsets](bios_setup_var_offsets.md) | Verified InsydeH2O Setup offsets on this chassis. |

Installer scripts and EFI files live in [`tools/OpenCore_PreyBoost_EFI/`](../tools/OpenCore_PreyBoost_EFI/README.md).

## Linux

See the [Linux documentation](linux/README.md) for the native Linux port, installation, hardware interfaces, audio, tests and recovery.
