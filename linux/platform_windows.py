"""Platform Windows: Strict split between Platform Settings and Advanced (Power Profiles / ACPI).

Matches:
- PreySense.Frontend/Views/AdvancedSettingsWindow.xaml (Platform Settings, 540px)
- PreySense.Frontend/Views/AdvancedWindow.xaml (Advanced: Power Profiles by source + ACPI Override, 540px)
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame
)
try:
    from ui_controls import (
        SettingSwitchRow, SettingSliderRow, SettingDropdownRow,
        SettingActionRow, SettingValueRow
    )
    from window_chrome import WindowTitleBar
    from appearance import LANGUAGES
except ImportError:
    from linux.ui_controls import (
        SettingSwitchRow, SettingSliderRow, SettingDropdownRow,
        SettingActionRow, SettingValueRow
    )
    from linux.window_chrome import WindowTitleBar
    from linux.appearance import LANGUAGES

def _fit_dialog_content(dialog):
    content=dialog._platform_content
    content.ensurePolished();content.layout().activate()
    dialog.layout().activate();dialog.adjustSize()



class _PlatformDialog(QDialog):
    def showEvent(self,event):
        # Theme/font polishing may change size hints since construction.
        _fit_dialog_content(self)
        super().showEvent(event)


def _make_frameless_dialog(parent, title_text, width=540):
    dialog = _PlatformDialog(parent)
    dialog.setWindowTitle(f"PreySense • {title_text}")
    dialog.setFixedWidth(width)
    dialog.setWindowFlags(dialog.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

    root_layout = QVBoxLayout(dialog)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)
    root_layout.addWidget(WindowTitleBar(dialog, title_text))

    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)
    content_layout.setContentsMargins(14, 10, 14, 8)
    # Setting rows already carry the source's 4px top/bottom margin.
    content_layout.setSpacing(0)
    root_layout.addWidget(content_widget)
    dialog._platform_content=content_widget
    from PySide6.QtWidgets import QLayout
    root_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

    return dialog, content_layout


def _separator(layout):
    """Windows Separator Margin=0,12, height1 and theme-owned line color."""
    container=QWidget()
    line_layout=QVBoxLayout(container);line_layout.setContentsMargins(0,12,0,12);line_layout.setSpacing(0)
    line=QFrame();line.setFixedHeight(1);line.setProperty('preysenseSeparator',True)
    line_layout.addWidget(line);container.setFixedHeight(25);layout.addWidget(container)


def build_platform_windows(window):
    """Constructs the two distinct dialogs matching AdvancedSettingsWindow and AdvancedWindow."""

    # ── 1. PLATFORM SETTINGS (AdvancedSettingsWindow.xaml) ──────────────────
    settings_dialog, s_layout = _make_frameless_dialog(window, "Settings", width=540)
    window.settings_dialog = settings_dialog

    # A. Run on Startup (Truthful label for Linux)
    row_startup = SettingSwitchRow("Run on Startup", checked=(Path.home() / ".config/autostart/preysense.desktop").exists())
    if hasattr(window, "set_autostart"):
        row_startup.toggled.connect(window.set_autostart)
    s_layout.addWidget(row_startup)
    window._row_startup = row_startup

    # B. Language
    row_lang = SettingDropdownRow("Language", dropdown_width=220)
    row_lang.combo.setProperty('preserveLanguageNames',True)
    for name, code in LANGUAGES.items(): row_lang.addItem(name, code)
    lang_val = window.settings.value("language", "en-US") if hasattr(window, "settings") else "en-US"
    row_lang.setCurrentIndex(max(0, row_lang.combo.findData(lang_val)))
    row_lang.currentIndexChanged.connect(lambda index: window.appearance.set_language(row_lang.combo.itemData(index)) if hasattr(window, "appearance") else None)
    s_layout.addWidget(row_lang)
    window._row_lang = row_lang

    # C. Theme
    theme_val = window.settings.value("theme", "Dark") if hasattr(window, "settings") else "Dark"
    is_light = theme_val == "Light"
    row_theme = SettingSwitchRow("Theme", checked=is_light, on_text="Light", off_text="Dark", width=92)
    row_theme.toggled.connect(lambda checked: window.appearance.set_theme("Light" if checked else "Dark") if hasattr(window, "appearance") else None)
    s_layout.addWidget(row_theme)
    window._row_theme = row_theme

    # Separator
    _separator(s_layout)

    # E. Battery Limit (80% / 100%)
    bat_val = int(window.settings.value("battery_limit", 80)) if hasattr(window, "settings") else 80
    bat_limit_80 = bat_val == 80
    row_battery = SettingSwitchRow("Battery Limit", checked=bat_limit_80, on_text="80%", off_text="100%", width=92)
    if hasattr(window, "apply"):
        row_battery.toggled.connect(lambda checked: window.apply("battery_limit", 80 if checked else 100))
    s_layout.addWidget(row_battery)
    window._row_battery = row_battery

    # G. BlueLight Shield


    # I. USB Power-Off Charging (Snapping 0/10/20/30, release-only commit)
    usb_val = int(window.settings.value("usb_charging", 0)) if hasattr(window, "settings") else 0
    row_usb = SettingSliderRow("USB Power-Off Charging", 0, 30, usb_val, unit="%")
    row_usb.slider.setSingleStep(10)
    row_usb.slider.setTickInterval(10)
    if hasattr(window, "apply"):
        def commit_usb():
            value=max(0,min(30,((row_usb.slider.value()+5)//10)*10))
            row_usb.setValue(value)
            window.apply("usb_charging",value)
        row_usb.slider.sliderReleased.connect(commit_usb)
    s_layout.addWidget(row_usb)
    row_usb.label_value.setText('Off' if row_usb.value()==0 else f'{row_usb.value()}%')
    row_usb.valueChanged.connect(lambda value:row_usb.label_value.setText('Off' if value==0 else f'{value}%'))
    window._row_usb = row_usb

    # ── 2. ADVANCED / POWER PROFILES & ACPI (AdvancedWindow.xaml) ─────────
    adv_dialog=settings_dialog
    a_layout=s_layout
    _separator(a_layout)
    try:
        from source_profiles import SOURCE_PROFILE_NAMES
    except ImportError:
        from linux.source_profiles import SOURCE_PROFILE_NAMES
    modes_list = list(SOURCE_PROFILE_NAMES)

    # Section 1: Power Profiles by Source
    row_bat_prof = SettingDropdownRow("On Battery", dropdown_width=160)
    row_bat_prof.addItems(modes_list)
    bat_prof_val = window.settings.value("profile_battery", "Eco") if hasattr(window, "settings") else "Eco"
    row_bat_prof.setCurrentText(bat_prof_val)
    row_bat_prof.setEnabled(True)
    a_layout.addWidget(row_bat_prof)

    row_ac = SettingDropdownRow("On AC", dropdown_width=160)
    row_ac.addItems(modes_list)
    ac_prof_val = window.settings.value("profile_ac", "Balanced") if hasattr(window, "settings") else "Balanced"
    row_ac.setCurrentText(ac_prof_val)
    row_ac.setEnabled(True)
    a_layout.addWidget(row_ac)

    def configure_source(source,name):
        import json
        try:mapping=json.loads(window.settings.value('source_profiles','{}'))
        except (ValueError,TypeError):mapping={}
        mapping.setdefault('Battery','Eco')
        mapping.setdefault('AC','Balanced')
        mapping[source]=name
        window.settings.setValue('source_profiles',json.dumps(mapping))
        window.apply('source_profiles',mapping)
    if hasattr(window,'settings') and hasattr(window,'apply'):
        row_bat_prof.currentTextChanged.connect(lambda name:configure_source('Battery',name))
        row_ac.currentTextChanged.connect(lambda name:configure_source('AC',name))
        import json
        try:stored=json.loads(window.settings.value('source_profiles','{}'))
        except (ValueError,TypeError):stored={}
        stored.setdefault('Battery','Eco')
        for source,row in [('Battery',row_bat_prof),('AC',row_ac)]:
            row.combo.blockSignals(True)
            if source in stored:row.setCurrentText(stored[source])
            row.combo.blockSignals(False)


    for dialog in (settings_dialog,adv_dialog):
        _fit_dialog_content(dialog)
    from slider_snap import configure_snap
    configure_snap(row_usb.slider,10)
    return {"settings": settings_dialog, "advanced": settings_dialog}


def update_platform_windows(window, data):
    """Updates live telemetry for settings without overriding active user edits."""
    if hasattr(window,'_row_battery'):
        window._row_battery.setEnabled(str(data.get('battery_limit')) in ('80','100'))
    if hasattr(window,'_row_usb'):
        window._row_usb.setEnabled(str(data.get('usb_charging')) in ('0','10','20','30'))
    if hasattr(window, "_row_battery") and data.get("battery_limit"):
        is_80 = str(data["battery_limit"]).strip() == "80"
        window._row_battery.switch.blockSignals(True)
        window._row_battery.setChecked(is_80)
        window._row_battery.switch.blockSignals(False)

    if hasattr(window, "_row_usb") and data.get("usb_charging") is not None and not window._row_usb.slider.isSliderDown() and not window._row_usb.slider.hasFocus():
        try:
            val = int(data["usb_charging"])
            window._row_usb.slider.blockSignals(True)
            window._row_usb.setValue(val)
            window._row_usb.label_value.setText("Off" if val==0 else f"{val}%")
            window._row_usb.slider.blockSignals(False)
        except (ValueError, TypeError): pass
