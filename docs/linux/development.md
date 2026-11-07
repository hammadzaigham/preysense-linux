# Linux development and verification

The Windows WPF projects remain the visual reference. Linux runtime code is in
`linux/`; keep changes within retained features listed in [features](features.md).

- `preysense.py`: Qt lifecycle, worker, cached settings and command routing.
- `design.py`, `platform_windows.py`, `controls.py`, `window_chrome.py`: shell and controls.
- `hardware.py`, `kernel/`: bounded Acer WMI, HID and watchdog interfaces.
- `cpu_power.py`, `cpu_tuning.py`, `power_ownership.py`: Intel RAPL and restoration.
- `calibration.py`, `calibration_cycle.py`, `calibration_ui.py`: missing-only calibration.
- `fan_curve.py`: shared timing and hysteresis for custom fan targets.
- `display.py`, `gpu_mode.py`: KDE display and reboot-dependent firmware GPU choices.
- `hotkeys.py`, `power_events.py`: event-driven input and power-source notifications.
- `lighting_effects.py`, `lighting_animation.py`, `lighting_ui.py`: hardware/software RGB.
- `audio.py`, `audio_ui.py`: AcerUltraX integration.
- `metrics_overlay.py`, `cpu_telemetry.py`, `nvml_telemetry.py`: demand-based metrics.
- `memory_reader.py`: one-time configured RAM speed read in the hardware helper.

```sh
python3 -m py_compile linux/*.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s linux/tests -v
QT_QPA_PLATFORM=offscreen python3 linux/tests/gui_smoke.py
make -C linux/kernel
```

Some Qt tests create application objects; run isolated test files if a test
order mixes QCoreApplication and QApplication. The GUI smoke check uses live
available reads and normal cleanup; it can restore firmware fan Auto on exit.
Unit fixtures use temporary sysfs/mock interfaces. Never call a synthetic event
an observed physical press or accepted firmware storage proof of visible effect.

Source and installed `/opt/preysense` copies can differ. Deploy exact reviewed
files and required services together, then verify the installed launch log.
Do not reset shared uncommitted work. Keep original Windows sources intact.
No runtime GPU unbind or reboot is required for ordinary UI checks.
