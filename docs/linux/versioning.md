# Application version1.0.0

The Linux application release is **1.0.0**, defined once in
`linux/version.py` as `__version__`. The dashboard subtitle and `preysense --version`
should both read this constant. `linux/install.sh` already copies all top-level
Python modules, including this file.

The installed OEM hardware bridge and DKMS package keep their existing internal
version **2.5.0**. Application renumbering must not rename its registered DKMS
version, ABI, `/usr/src/preysense-2.5.0` tree, build/install/uninstall commands or
module signing configuration. Those are independent of the visible app version.

## Read-only version-location audit

Linux product labels to wire to `version.__version__`:

- `linux/design.py`: main `WindowTitleBar` subtitle.
- `linux/preysense.py`: argparse `--version` string.
- `linux/README.md`: Linux release text.

Original Windows product version locations, if intentionally renumbering the
Windows application as well:

- `PreySense.Frontend/PreySense.Frontend.csproj`: `Version`, `AssemblyVersion`,
  `FileVersion` (assembly/file values use four components).
- `PreySense.Frontend/Services/UpdateCheckService.cs`: `CurrentVersion`.
- `PreySense.Frontend/MainWindow.xaml`: title-bar subtitle.
- Root `README.md`: existing Windows release announcement.

This Linux change leaves the Windows project untouched. The main integration
owner decides the Windows scope and wires the shared Linux product labels.
