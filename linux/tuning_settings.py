"""Windows-style master tuning controls and staged global PROCHOT settings."""
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
    from cpu_prochot import CpuProchot
    from design import action

    dialog, layout = _make_frameless_dialog(window, 'Tuning Settings')
    switches = (
        ('Enable CPU Power Limit Control', 'enable_cpu_power_limits', True),
        ('Enable GPU Power Limit Control', 'enable_gpu_power_limits', True),
    )

    def update_master(key, value):
        window.settings.setValue(key, value)
        refresh = getattr(window, 'refresh_tuning_master_switches', None)
        if refresh:
            refresh()

    for label, key, default in switches:
        switch = SettingSwitchRow(label, checked=window.settings.value(key, default, type=bool))
        if key == 'enable_gpu_power_limits':
            switch.setEnabled(getattr(window, 'gpu_offsets_available', False))
        switch.toggled.connect(lambda value, key=key: update_master(key, value))
        layout.addWidget(switch)

    _separator(layout)
    readout = QHBoxLayout()
    activation = QLabel('PROCHOT —')
    tjmax = QLabel('Tj-Max —')
    readout.addWidget(activation)
    readout.addStretch()
    readout.addWidget(tjmax)
    layout.addLayout(readout)

    fields = QHBoxLayout()
    fields.setSpacing(12)
    offset = SettingValueRow('CPU PROCHOT Offset', 0, '°C', 0, 63)
    include = RectangularSwitch()
    include.setAccessibleName('Include PROCHOT offset')
    fields.addWidget(offset, 1)
    fields.addWidget(include)
    layout.addLayout(fields)
    status = QLabel()
    status.setWordWrap(True)
    status.hide()
    layout.addWidget(status)
    save = action('Save')
    layout.addWidget(save)

    snapshot = None

    def refresh_readout():
        activation.setText('PROCHOT —')
        tjmax.setText('Tj-Max —')
        if snapshot is not None:
            suffix = ' - Locked' if snapshot.locked else ''
            activation.setText(f'PROCHOT {snapshot.tjmax_celsius - offset.value()}°C{suffix}')
            tjmax.setText(f'Tj-Max {snapshot.tjmax_celsius}°C')
        offset.setEnabled(include.isEnabled() and include.isChecked())

    def show(event):
        nonlocal snapshot
        snapshot = CpuProchot().read()
        if snapshot is not None and window.settings.value('factory_prochot_offset', None) is None:
            window.settings.setValue('factory_prochot_offset', snapshot.offset_celsius)
            window.settings.setValue('factory_tjmax', snapshot.tjmax_celsius)
            window.settings.setValue('factory_prochot_locked', snapshot.locked)
        fallback = snapshot.offset_celsius if snapshot is not None else 0
        offset.setValue(window.settings.value('prochot_offset', fallback, type=int))
        include.setEnabled(snapshot is not None and not snapshot.locked)
        include.setChecked(include.isEnabled() and window.settings.value('apply_prochot', False, type=bool))
        refresh_readout()
        status.hide()
        QDialog.showEvent(dialog, event)

    def save_settings():
        if include.isEnabled():
            try:
                offset.spin.interpretText()
                window.settings.setValue('prochot_offset', offset.value())
                window.settings.setValue('apply_prochot', include.isChecked())
            except (OSError, ValueError) as exc:
                status.setText(f'Could not save PROCHOT: {exc}')
                status.show()
                dialog.adjustSize()
                return
        dialog.close()

    include.toggled.connect(refresh_readout)
    offset.valueChanged.connect(refresh_readout)
    save.clicked.connect(save_settings)
    dialog.showEvent = show
    dialog.adjustSize()
    return dialog
