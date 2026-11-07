"""Windows Lighting window order and palettes, using the existing Linux command API."""
ZONE_PRESETS = {'predator': ['#00E5FF', '#00E5FF', '#00E5FF', '#FFFFFF'], 'cyberpunk': ['#FFDF00', '#FF007F', '#00E5FF', '#9D4EDD'], 'fireice': ['#00E5FF', '#0077B6', '#FFB703', '#E71D36'], 'matrix': ['#00FF66', '#2EC4B6', '#00FF66', '#00FF66'], 'sunset': ['#FF6B00', '#FF3D5A', '#C9184A', '#7209B7'], 'ocean': ['#003566', '#0077B6', '#00B4D8', '#CAF0F8'], 'ember': ['#6A040F', '#DC2F02', '#F48C06', '#FFBA08'], 'vaporwave': ['#FF71CE', '#B967FF', '#01CDFE', '#05FFA1'], 'royal': ['#3C096C', '#5A189A', '#FFD60A', '#FFFFFF'], 'arctic': ['#ADE8F4', '#FFFFFF', '#48CAE4', '#0077B6'], 'sakura': ['#FF8FAB', '#FFB3C6', '#FFFFFF', '#FB6F92'], 'rainbow': ['#FF0000', '#FFD000', '#00E676', '#2979FF'], 'toxic': ['#C8FF00', '#7CFC00', '#39FF14', '#0B6E4F'], 'lava': ['#8B0000', '#FF0000', '#FF4500', '#FF6B00'], 'midnight': ['#10002B', '#3A0CA3', '#4361EE', '#4CC9F0'], 'dracula': ['#BD93F9', '#FF79C6', '#8BE9FD', '#50FA7B'], 'stealth': ['#FFFFFF', '#FFFFFF', '#FFFFFF', '#FFFFFF']}
LOGO_PRESETS = {'Predator': '#00E5FF', 'Fire': '#FF0033', 'Amber': '#F59E0B', 'Neon': '#FF007F', 'Matrix': '#00FF66', 'White': '#FFFFFF', 'Purple': '#8B00FF', 'Sunset': '#FF6B00', 'Ocean': '#0077B6', 'Sakura': '#FF8FAB', 'Toxic': '#39FF14', 'Lava': '#FF4500', 'Midnight': '#3A0CA3', 'Ice': '#48CAE4', 'Vapor': '#FF71CE'}
ZONE_OPTIONS = [('Custom', 'Custom'), ('Predator', 'Predator'), ('Cyberpunk', 'Cyberpunk'), ('Fire & Ice', 'FireIce'), ('Matrix', 'Matrix'), ('Stealth', 'Stealth'), ('Sunset', 'Sunset'), ('Ocean', 'Ocean'), ('Ember', 'Ember'), ('Vaporwave', 'Vaporwave'), ('Royal', 'Royal'), ('Arctic', 'Arctic'), ('Sakura', 'Sakura'), ('Rainbow', 'Rainbow'), ('Toxic', 'Toxic'), ('Lava', 'Lava'), ('Midnight', 'Midnight'), ('Dracula', 'Dracula')]
LOGO_OPTIONS = [('Custom', 'Custom'), ('Predator Cyan', 'Predator'), ('Hellfire Red', 'Fire'), ('Tactical Amber', 'Amber'), ('Cyber Neon', 'Neon'), ('Matrix Green', 'Matrix'), ('Arctic White', 'White'), ('Deep Violet', 'Purple'), ('Sunset Orange', 'Sunset'), ('Ocean Blue', 'Ocean'), ('Sakura Pink', 'Sakura'), ('Toxic Lime', 'Toxic'), ('Lava Orange', 'Lava'), ('Midnight Indigo', 'Midnight'), ('Ice Blue', 'Ice'), ('Vaporwave Pink', 'Vapor')]

from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QSlider,QLineEdit,QScrollArea
from dialog_base import AudioDialog,AudioSwitch,button,row
from controls import ColorWheel
from hardware import EFFECTS
from lighting_effects import SOFTWARE_EFFECTS
from appearance import color as theme_color


class ColorSwatch(QWidget):
    """Original22px color preview beside the centered hex editor."""
    def __init__(self):
        super().__init__();self.setFixedSize(22,22);self.color=QColor('#28d8ca')
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme_color('BorderMainColor','#373737')),1))
        painter.setBrush(self.color);painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),3,3)


def color_editor():
    panel=QWidget();layout=QHBoxLayout(panel);layout.setContentsMargins(0,10,0,0);layout.setSpacing(8)
    layout.addStretch();label=QLabel('Color:');label.setStyleSheet('font-weight:600;');layout.addWidget(label)
    swatch=ColorSwatch();layout.addWidget(swatch)
    field=QLineEdit();field.setFixedSize(80,26);field.setAlignment(Qt.AlignCenter)
    field.setStyleSheet('font-family:Consolas,monospace;font-size:12px;font-weight:600;')
    layout.addWidget(field);layout.addStretch()
    return panel,field,swatch



def build_lighting_window(window):
    """Called after finish_control_windows; no command is sent during construction.

    Underlying effect/speed widgets remain the stable command API. Visible modes
    translate only verified hardware effects; unsupported Windows choices stay
    disabled. User edits apply live; construction and target navigation never write.
    """
    previous=window.dialogs['Lighting'];previous.hide()
    dialog=AudioDialog(window,'Lighting',500);window.dialogs['Lighting']=dialog
    content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
    dialog.body.addWidget(content)
    from PySide6.QtWidgets import QLayout
    dialog.root.setSizeConstraint(QLayout.SetDefaultConstraint)
    def fit_height():
        layout.invalidate();layout.activate();dialog.body.invalidate();dialog.root.invalidate();dialog.root.activate()
        dialog.setFixedHeight(dialog.root.sizeHint().height())
        dialog.setFixedWidth(500)

    # These controls feed existing apply_lighting and telemetry; remove old UI-only
    # signals where necessary to prevent the superseded dialog changing drafts.
    for widget in (window.effect,window.speed):widget.setParent(dialog);widget.hide()
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        try:window.effect.currentIndexChanged.disconnect()
        except RuntimeError:pass
    target_states=window.lighting_target_states
    selected=[0];loading=[False]
    apply_timer=QTimer(dialog);apply_timer.setSingleShot(True);apply_timer.setInterval(80)
    def commit_live():
        if loading[0]:return
        if window.lighting_target=='Logo' and sync_logo.isChecked() and power.isChecked():
            state=target_states['Keyboard']
            window.apply('lighting',dict(colors=[(c.red(),c.green(),c.blue()) for c in state['colors']],
                brightness=state['brightness'],effect=state['effect'],speed=state['speed'],sync_logo=True))
        else:
            window.apply_lighting()
    apply_timer.timeout.connect(commit_live)
    def request_apply(*_):
        if not loading[0]:apply_timer.start()
    def flush_pending():
        if apply_timer.isActive():apply_timer.stop();commit_live()

    def reflect_keyboard_brightness(value):
        if window.lighting_target!='Keyboard':return
        loading[0]=True
        try:window.brightness.setValue(value)
        finally:loading[0]=False

    brightness_label=QLabel();row(layout,'Brightness',brightness_label)
    layout.addWidget(window.brightness)
    window.brightness.valueChanged.connect(lambda v:brightness_label.setText(f'{v}%'))
    brightness_label.setText(f'{window.brightness.value()}%')
    timeout=window.original_timeout;timeout.setParent(content)
    timeout.setRange(0, 120);timeout.setSingleStep(10);timeout.setPageStep(30)
    timeout_label=QLabel('OFF' if not timeout.value() else f'{timeout.value()} s');row(layout,'Backlight Timeout',timeout_label)
    layout.addWidget(timeout);timeout.valueChanged.connect(lambda v:timeout_label.setText('OFF' if not v else f'{v} s'))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        try:timeout.sliderReleased.disconnect()
        except RuntimeError:pass
    timeout.sliderReleased.connect(lambda:window.apply('led_timeout', timeout.value()))
    tabs=QHBoxLayout();keyboard=button('Keyboard');logo=button('Logo')
    for item in (keyboard,logo):item.setCheckable(True);tabs.addWidget(item)
    layout.addLayout(tabs)
    keyboard_panel=QWidget();kb=QVBoxLayout(keyboard_panel);kb.setContentsMargins(0,0,0,0);kb.setSpacing(8)
    mode=QComboBox();mode.addItems(['Static','Dynamic','Software']);mode.setFixedWidth(154);row(kb,'Lighting Mode',mode)
    sync_panel=QWidget();sync_layout=QVBoxLayout(sync_panel);sync_layout.setContentsMargins(0,0,0,0)
    sync=AudioSwitch();sync.setChecked(True);sync_label=row(sync_layout,'Sync All Zones',sync);kb.addWidget(sync_panel)
    preset=QComboBox()
    for text,key in ZONE_OPTIONS:preset.addItem(text,key)
    preset_panel=QWidget();pl=QVBoxLayout(preset_panel);pl.setContentsMargins(0,0,0,0);row(pl,'Preset Themes',preset)
    preset.setFixedWidth(210)
    kb.addWidget(preset_panel)
    zones=QWidget();zl=QHBoxLayout(zones);zl.setContentsMargins(0,0,0,0)
    for index,item in enumerate(window.color_buttons):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            try:item.clicked.disconnect()
            except RuntimeError:pass
        item.setText(f'Zone {index+1}');item.setMinimumHeight(32);item.setMaximumHeight(32);zl.addWidget(item)
    kb.addWidget(zones)
    wheel=ColorWheel();wheel.setFixedSize(140,140);kb.addWidget(wheel,0,Qt.AlignHCenter)
    hexrow,hexedit,hex_swatch=color_editor();kb.addWidget(hexrow)
    effect_combo=QComboBox();effect_row=QWidget();el=QVBoxLayout(effect_row);el.setContentsMargins(0,0,0,0)
    effect_combo.setFixedWidth(210);effect_label=row(el,'Dynamic Effect',effect_combo);el.itemAt(0).layout().setContentsMargins(0,0,0,4);kb.addWidget(effect_row)
    speed=QSlider(Qt.Horizontal);speed.setRange(0,100);speed.setSingleStep(25);speed.setPageStep(25)
    speed_label=QLabel();speed_panel=QWidget();sl=QVBoxLayout(speed_panel);sl.setContentsMargins(0,0,0,0)
    row(sl,'Effect Speed',speed_label);sl.addWidget(speed);kb.addWidget(speed_panel)
    layout.addWidget(keyboard_panel)
    logo_panel=QWidget();ll=QVBoxLayout(logo_panel);ll.setContentsMargins(0,0,0,0);ll.setSpacing(8)
    power=AudioSwitch();row(ll,'Logo Backlight',power)
    old_sync_logo=window.sync_logo_checkbox;old_sync_logo.hide()
    sync_logo=AudioSwitch();sync_logo.setChecked(old_sync_logo.isChecked())
    sync_logo.toggled.connect(old_sync_logo.setChecked);window.sync_logo_checkbox=sync_logo
    row(ll,'Sync With Keyboard',sync_logo)
    logo_effect_panel=QWidget();lep=QVBoxLayout(logo_effect_panel);lep.setContentsMargins(0,0,0,0);ll.addWidget(logo_effect_panel)
    logo_mode=QComboBox();logo_mode.addItems(['Static','Breathing','Neon']);logo_mode.setFixedWidth(154);row(lep,'Effect Mode',logo_mode)
    logo_color_panel=QWidget();lcp=QVBoxLayout(logo_color_panel);lcp.setContentsMargins(0,0,0,0);lcp.setSpacing(8);ll.addWidget(logo_color_panel)
    logo_preset=QComboBox()
    for text,key in LOGO_OPTIONS:logo_preset.addItem(text,key)
    logo_preset.setFixedWidth(210);row(lcp,'Preset Themes',logo_preset)
    logo_wheel=ColorWheel();logo_wheel.setFixedSize(140,140);lcp.addWidget(logo_wheel,0,Qt.AlignHCenter)
    logo_hexrow,logo_hex,logo_swatch=color_editor();lcp.addWidget(logo_hexrow)
    logo_speed_panel=QWidget();lsp=QVBoxLayout(logo_speed_panel);lsp.setContentsMargins(0,0,0,0);ll.addWidget(logo_speed_panel)
    logo_speed=QSlider(Qt.Horizontal);logo_speed.setRange(0,100);logo_speed_label=QLabel()
    row(lsp,'Animation Speed',logo_speed_label);lsp.addWidget(logo_speed)
    layout.addWidget(logo_panel)
    window.rgb_apply.setParent(previous);window.rgb_apply.hide()
    window.rgb_status.setParent(previous);window.rgb_status.hide()
    hardware_options=[('Breathing','Breathing'),('Neon Wave','Neon'),('Color Wave','Wave'),('Ripple',None),('Zoom','Zoom'),('Snake',None),('Disco',None)]
    # Retain Linux-supported effects as choices after the original Windows list.
    hardware_options += [(name,name) for name in EFFECTS if name not in ('Static','Breathing','Neon','Wave','Zoom')]
    def api_effect(value):
        window.effect.blockSignals(True)
        if window.effect.findText(value)<0:window.effect.addItem(value)
        window.effect.setCurrentText(value);window.effect.blockSignals(False)
    def paint():
        target=window.lighting_target
        current=window.colors[0] if target=='Logo' else window.colors[selected[0]]
        chosen=logo_wheel if target=='Logo' else wheel;field=logo_hex if target=='Logo' else hexedit
        chosen.color=QColor(current);chosen.update();field.setText(current.name().upper())
        swatch=logo_swatch if target=='Logo' else hex_swatch;swatch.color=QColor(current);swatch.update()
        window.paint_colors()
        for item in window.color_buttons:item.setStyleSheet(item.styleSheet().replace('min-height:64px','min-height:32px'))
    def changed(color):
        if loading[0]:return
        if window.lighting_target=='Logo' or sync.isChecked():window.colors=[QColor(color) for _ in range(4)]
        else:window.colors[selected[0]]=QColor(color)
        paint()
        request_apply()
    wheel.changed.connect(changed);logo_wheel.changed.connect(changed)
    def commit(field):
        value=QColor(field.text())
        if value.isValid():changed(value)
        else:paint()
    hexedit.editingFinished.connect(lambda:commit(hexedit));logo_hex.editingFinished.connect(lambda:commit(logo_hex))
    def choose_zone(index):selected[0]=index;paint()
    for index,item in enumerate(window.color_buttons):item.clicked.connect(lambda checked=False,i=index:choose_zone(i))
    def visibility():
        static=mode.currentText()=='Static';is_keyboard=window.lighting_target=='Keyboard'
        sync_panel.setVisible(static);sync.setVisible(static);sync_label.setVisible(static);preset_panel.setVisible(static and not sync.isChecked());zones.setVisible(static and not sync.isChecked())
        wheel.setVisible(static);hexrow.setVisible(static);effect_row.setVisible(not static);speed_panel.setVisible(not static)
        independent=power.isChecked() and not sync_logo.isChecked()
        window.brightness.setEnabled(is_keyboard or independent)
        sync_logo.setEnabled(power.isChecked())
        for item in (logo_mode,logo_preset,logo_wheel,logo_hex):item.setEnabled(independent)
        logo_speed.setEnabled(independent and logo_mode.currentText()!='Static')
        logo_effect_panel.setVisible(not sync_logo.isChecked())
        logo_color_panel.setVisible(not sync_logo.isChecked() and logo_mode.currentText()=='Static')
        logo_speed_panel.setVisible(not sync_logo.isChecked() and logo_mode.currentText()!='Static')
        QTimer.singleShot(0,fit_height)
    def choose_mode(_=None,desired=None):
        effect_combo.blockSignals(True);effect_combo.clear()
        options=[(name,name) for name in SOFTWARE_EFFECTS] if mode.currentText()=='Software' else hardware_options
        for text,value in options:
            effect_combo.addItem(text,value)
            if value is None:effect_combo.model().item(effect_combo.count()-1).setEnabled(False)
        index=effect_combo.findData(desired) if desired is not None else 0;effect_combo.setCurrentIndex(max(0,index));effect_combo.blockSignals(False)
        effect_label.setText('Software Effect' if mode.currentText()=='Software' else 'Dynamic Effect')
        if not loading[0]:
            api_effect('Static' if mode.currentText()=='Static' else effect_combo.currentData())
            request_apply()
        visibility()
    mode.currentIndexChanged.connect(choose_mode)
    effect_combo.currentIndexChanged.connect(lambda _: (api_effect(effect_combo.currentData()), request_apply()) if not loading[0] and effect_combo.currentData() else None)
    def sync_zones(enabled):
        visibility()
        if not loading[0] and enabled:
            window.colors=[QColor(window.colors[selected[0]]) for _ in range(4)]
            paint()
        request_apply()
    sync.toggled.connect(sync_zones)
    window.brightness.valueChanged.connect(request_apply)
    def set_speed(value):
        speed_label.setText(f'{value}%');logo_speed_label.setText(f'{value}%')
        if not loading[0]:
            window.speed.setValue(round(value/10))
            request_apply()
    speed.valueChanged.connect(set_speed);logo_speed.valueChanged.connect(set_speed)
    def apply_preset(combo,cover=False):
        key=combo.currentData()
        if loading[0] or key=='Custom':return
        values=[LOGO_PRESETS[key]]*4 if cover and key in LOGO_PRESETS else ZONE_PRESETS.get(str(key).lower())
        if values:
            window.colors=[QColor(value) for value in values]
            paint()
            request_apply()
    preset.currentIndexChanged.connect(lambda _:apply_preset(preset));logo_preset.currentIndexChanged.connect(lambda _:apply_preset(logo_preset,True))
    def logo_effect():
        if not loading[0]:
            if not power.isChecked():sync_logo.setChecked(False)
            api_effect(logo_mode.currentText() if power.isChecked() else 'Off')
            request_apply()
        visibility()
    power.toggled.connect(logo_effect);logo_mode.currentIndexChanged.connect(logo_effect)
    def sync_cover(enabled):
        visibility();request_apply()
    sync_logo.toggled.connect(sync_cover)
    def select_target(name,initial=False):
        if not initial:
            flush_pending()
            target_states[window.lighting_target]=dict(colors=[QColor(c) for c in window.colors],brightness=window.brightness.value(),effect=window.effect.currentText(),speed=window.speed.value())
        loading[0]=True
        try:
            window.lighting_target=name;state=target_states[name]
            window.colors=[QColor(c) for c in state['colors']];window.brightness.setValue(state['brightness']);window.speed.setValue(state['speed'])
            api_effect(state['effect']);selected[0]=0;keyboard.setChecked(name=='Keyboard');logo.setChecked(name=='Logo')
            keyboard_panel.setVisible(name=='Keyboard');logo_panel.setVisible(name=='Logo')
            value=state['speed']*10;speed.setValue(value);logo_speed.setValue(value);set_speed(value)
            if name=='Keyboard':
                mode.setCurrentText('Software' if state['effect'] in SOFTWARE_EFFECTS else 'Static' if state['effect']=='Static' else 'Dynamic');choose_mode(desired=state['effect'])
            else:power.setChecked(state['effect']!='Off');logo_mode.setCurrentText(state['effect'] if state['effect']!='Off' else 'Static')
            paint();visibility()
        finally:loading[0]=False
        QTimer.singleShot(0,fit_height)
    keyboard.clicked.connect(lambda:select_target('Keyboard'));logo.clicked.connect(lambda:select_target('Logo'))
    def preview(colors):
        if window.lighting_target=='Keyboard' and mode.currentText()=='Software':
            for item,value in zip(window.color_buttons,colors):item.setStyleSheet(f'background:rgb{tuple(value)};min-height:32px;')
    window.worker.lighting_frame.connect(preview)
    window.lighting_ui=dict(mode=mode,preset=preset,sync=sync,keyboard=keyboard,logo=logo,effect=effect_combo,speed=speed,logo_mode=logo_mode,logo_power=power,logo_preset=logo_preset,wheel=wheel,logo_wheel=logo_wheel,hex=hexedit,logo_hex=logo_hex,sync_logo=sync_logo,apply_timer=apply_timer,select_target=select_target,flush_pending=flush_pending,reflect_keyboard_brightness=reflect_keyboard_brightness)
    select_target(getattr(window,'lighting_target','Keyboard'),True)
    from slider_snap import configure_snap
    configure_snap(window.brightness,25)
    configure_snap(timeout,10,30)
    configure_snap(speed,25);configure_snap(logo_speed,25)
    fit_height()
    return dialog
