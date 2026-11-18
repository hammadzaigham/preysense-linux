"""Tuning Settings Dialog for PreySense Linux.

Matches PreySense.Frontend/Views/TuningSettingsWindow.xaml (460px):
- Master Switches:
  - Enable CPU Boost Tuning
  - Enable CPU Power Limit Control
  - Enable GPU Power Limit Control
  - Enable GPU Overclocking
- PROCHOT Section:
  - CPU PROCHOT Offset value row
  - Apply switch
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame
)
try:
    from ui_controls import SettingSwitchRow, SettingValueRow, RectangularSwitch
    from window_chrome import WindowTitleBar
except ImportError:
    from linux.ui_controls import SettingSwitchRow, SettingValueRow, RectangularSwitch
    from linux.window_chrome import WindowTitleBar


def _make_frameless_dialog(parent, title_text, width=460):
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"PreySense • {title_text}")
    dialog.setFixedWidth(width)
    dialog.setWindowFlags(dialog.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

    root_layout = QVBoxLayout(dialog)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)
    root_layout.addWidget(WindowTitleBar(dialog, title_text))

    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)
    content_layout.setContentsMargins(14, 10, 14, 12)
    content_layout.setSpacing(6)
    root_layout.addWidget(content_widget)
    dialog._platform_content = content_widget

    return dialog, content_layout


def _separator(layout):
    container = QWidget()
    line_layout = QVBoxLayout(container)
    line_layout.setContentsMargins(0, 8, 0, 8)
    line_layout.setSpacing(0)
    line = QFrame()
    line.setFixedHeight(1)
    line.setProperty('preysenseSeparator', True)
    line_layout.addWidget(line)
    container.setFixedHeight(17)
    layout.addWidget(container)


def build_tuning_settings_dialog(window):
    dialog, layout = _make_frameless_dialog(window, "Tuning Settings", width=460)

    # Master Toggles
    sw_boost = SettingSwitchRow(
        "Enable CPU Boost Tuning",
        checked=bool(window.settings.value("enable_cpu_boost_tuning", True, type=bool))
    )
    sw_cpu = SettingSwitchRow(
        "Enable CPU Power Limit Control",
        checked=bool(window.settings.value("enable_cpu_power_limits", False, type=bool))
    )
    sw_gpu = SettingSwitchRow(
        "Enable GPU Power Limit Control",
        checked=bool(window.settings.value("enable_gpu_power_limits", False, type=bool))
    )
    sw_gpu_oc = SettingSwitchRow(
        "Enable GPU Overclocking",
        checked=bool(window.settings.value("enable_gpu_overclocking", False, type=bool))
    )

    def on_boost_toggled(checked):
        window.settings.setValue("enable_cpu_boost_tuning", bool(checked))
        if hasattr(window, 'refresh_tuning_master_switches'):
            window.refresh_tuning_master_switches()

    def on_cpu_toggled(checked):
        window.settings.setValue("enable_cpu_power_limits", bool(checked))
        if hasattr(window, 'refresh_tuning_master_switches'):
            window.refresh_tuning_master_switches()

    def on_gpu_toggled(checked):
        window.settings.setValue("enable_gpu_power_limits", bool(checked))
        if hasattr(window, 'refresh_tuning_master_switches'):
            window.refresh_tuning_master_switches()

    def on_gpu_oc_toggled(checked):
        window.settings.setValue("enable_gpu_overclocking", bool(checked))
        if hasattr(window, 'refresh_tuning_master_switches'):
            window.refresh_tuning_master_switches()

    sw_boost.toggled.connect(on_boost_toggled)
    sw_cpu.toggled.connect(on_cpu_toggled)
    sw_gpu.toggled.connect(on_gpu_toggled)
    sw_gpu_oc.toggled.connect(on_gpu_oc_toggled)

    layout.addWidget(sw_boost)
    layout.addWidget(sw_cpu)
    layout.addWidget(sw_gpu)
    layout.addWidget(sw_gpu_oc)

    _separator(layout)

    # PROCHOT Section
    prochot_block = QWidget()
    prochot_l = QVBoxLayout(prochot_block)
    prochot_l.setContentsMargins(0, 0, 0, 0)
    prochot_l.setSpacing(4)

    prochot_labels = QHBoxLayout()
    prochot_act = QLabel('PROCHOT —')
    tjmax_lab = QLabel('Tj-Max —')
    for lab in (prochot_act, tjmax_lab):
        lab.setObjectName('muted')
    prochot_labels.addWidget(prochot_act)
    prochot_labels.addStretch()
    prochot_labels.addWidget(tjmax_lab)
    prochot_l.addLayout(prochot_labels)

    prochot_row = QHBoxLayout()
    prochot_offset = SettingValueRow('CPU PROCHOT Offset', 0, '°C', 0, 63)
    prochot_switch = RectangularSwitch()

    saved_prochot = window.settings.value('prochot_offset', None)
    if saved_prochot is not None:
        try:
            prochot_offset.setValue(int(saved_prochot))
        except (TypeError, ValueError):
            pass
    prochot_switch.setChecked(bool(window.settings.value('apply_prochot', False, type=bool)))

    def on_prochot_changed(val):
        window.settings.setValue('prochot_offset', int(val))
        if hasattr(window, 'prochot_offset'):
            window.prochot_offset.setValue(int(val))

    def on_prochot_switch(checked):
        window.settings.setValue('apply_prochot', bool(checked))
        if hasattr(window, 'prochot_switch'):
            window.prochot_switch.blockSignals(True)
            window.prochot_switch.setChecked(bool(checked))
            window.prochot_switch.blockSignals(False)

    prochot_offset.valueChanged.connect(on_prochot_changed)
    prochot_switch.toggled.connect(on_prochot_switch)

    prochot_row.addWidget(prochot_offset, 1)
    prochot_row.addWidget(prochot_switch)
    prochot_l.addLayout(prochot_row)
    layout.addWidget(prochot_block)

    def refresh_prochot_readouts():
        tjmax = window.settings.value('factory_tjmax', None)
        offset = window.settings.value('prochot_offset', None)
        if tjmax is not None:
            tjmax_lab.setText(f'Tj-Max {tjmax}°C')
            if offset is not None:
                try:
                    activation = int(tjmax) - int(offset)
                    prochot_act.setText(f'PROCHOT {activation}°C')
                except (TypeError, ValueError):
                    prochot_act.setText('PROCHOT —')
            else:
                prochot_act.setText('PROCHOT —')
        else:
            tjmax_lab.setText('Tj-Max —')
            prochot_act.setText('PROCHOT —')

    dialog.refresh_prochot_readouts = refresh_prochot_readouts
    refresh_prochot_readouts()

    dialog.adjustSize()
    return dialog
