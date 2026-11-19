"""Qt rendering of the existing PreySense WPF shell, tokens, icons and navigation."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QDialog,QComboBox,QApplication,QSlider,QSizePolicy
from hardware import MODES
from version import __version__

ASSETS=Path(__file__).resolve().parent/'assets'

def get_dpr():
    app = QApplication.instance()
    if app and app.primaryScreen():
        return app.primaryScreen().devicePixelRatio()
    return 1.0

from icon_assets import themed_icon,themed_pixmap,svg_mode_pixmap

def icon(filename,size=16):return themed_icon(filename,size)
def mode_pixmap(name,size=18):return svg_mode_pixmap(name,size)

def render_svg(path_or_data, size=18):
    dpr = get_dpr()
    data = path_or_data if isinstance(path_or_data, (bytes, bytearray)) else Path(path_or_data).read_bytes()
    renderer = QSvgRenderer(data)
    phys_size = int(round(size * dpr))
    pixmap = QPixmap(phys_size, phys_size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap

def action(text,filename=None,height=34):
    b=QPushButton(text); b.setMinimumHeight(height)
    if filename: b.setProperty('assetIcon',filename); b.setIcon(icon(filename)); b.setIconSize(QSize(16,16))
    return b

def build(window):
    # Match Typography.xaml's Segoe UI / system sans-serif fallback, not the unused animation font.
    font=QFont();font.setFamilies(['Segoe UI','sans-serif']);font.setPointSizeF(9);window.setFont(font)
    # Reuse tested functional pages as separate windows, as in the original app.
    window.dialogs={}
    names={'Lighting':(580,430),'Fans':(590,610),'Tuning':(520,360),'System':(660,740)}
    for i in reversed(range(window.tabs.count())):
        name=window.tabs.tabText(i)
        if name not in names: continue
        page=window.tabs.widget(i); window.tabs.removeTab(i)
        dialog=QDialog(window); dialog.setWindowTitle('PreySense · '+('Advanced' if name=='System' else name)); dialog.resize(*names[name]); dialog.setWindowIcon(window.windowIcon())
        dl=QVBoxLayout(dialog); dl.setContentsMargins(16,16,16,16); dl.addWidget(page);page.show()
        window.dialogs[name]=dialog
    fanpage=window.dialogs['Fans'].layout()
    controls=QHBoxLayout(); controls.addWidget(window.fan_auto); controls.addWidget(window.fan_max); controls.addWidget(window.fan_current)
    fanpage.insertLayout(0,controls)
    advanced=window.dialogs['System'].layout()
    charge=QHBoxLayout();charge.addWidget(window.battery);charge.addWidget(window.charge);charge.addWidget(window.charge_apply);advanced.insertLayout(0,charge)
    for name in ('Tuning','System'):
        d=window.dialogs[name];d.setWindowFlags(d.windowFlags()|Qt.FramelessWindowHint)
        title=QHBoxLayout();title.addWidget(QLabel('PreySense • '+('Advanced' if name=='System' else name)));title.addStretch()
        close=action('×',height=30);close.setFixedSize(30,30);close.setObjectName('titleButton');close.clicked.connect(d.hide);title.addWidget(close);d.layout().insertLayout(0,title)
        def press(event,d=d):
            if event.button()==Qt.LeftButton and event.position().y()<40 and d.windowHandle():d.windowHandle().startSystemMove()
        d.mousePressEvent=press
    # Keep diagnostic labels alive without exposing an alternative dashboard.
    old=window.takeCentralWidget();old.setParent(window);old.hide();window.functional_pages=old
    root=QWidget();root.setObjectName('shell')
    shell=QVBoxLayout(root);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
    settings=action('', 'icons8-settings-32.png',30);settings.setFixedSize(30,30);settings.setObjectName('titleButton');settings.clicked.connect(lambda:show_dialog(window,'Settings'))
    from window_chrome import WindowTitleBar
    shell.addWidget(WindowTitleBar(window,f'v{__version__}',on_close=window.close,actions=(settings,)))
    content=QWidget();layout=QVBoxLayout(content);layout.setContentsMargins(14,10,14,20);layout.setSpacing(12);shell.addWidget(content)
    def section(text,filename,metric=False):
        box=QWidget();vl=QVBoxLayout(box);vl.setContentsMargins(0,0,0,0);vl.setSpacing(10)
        heading=QHBoxLayout();label=QLabel();label.setProperty('assetPixmap',filename);label.setProperty('assetSize',16);label.setPixmap(themed_pixmap(filename,16));heading.addWidget(label);heading_text=QLabel(text);heading_text.setObjectName('sectionTitle');heading.addWidget(heading_text);heading.addStretch()
        sensor=QLabel('');sensor.setObjectName('sensor');heading.addWidget(sensor);vl.addLayout(heading);layout.addWidget(box)
        return vl,sensor
    modes,window.cpu_header=section('Performance Mode','icons8-gauge-32.png',True)
    row=QHBoxLayout();row.setSpacing(7);window.mode_tiles={}
    modeicons=['icons8-leaf-48.png','icons8-spa-flower-48.png','icons8-laptop-32.png','icons8-flash-48.png','icons8-rocket-32.png']
    for (name,value),filename in zip(MODES.items(),modeicons):
        tile=QPushButton();tile.setMinimumHeight(62);tile.setObjectName('modeTile');tile.setCheckable(True)
        inner=QVBoxLayout(tile);inner.setContentsMargins(2,6,2,6);inner.setSpacing(2)
        glyph=QLabel();glyph.setProperty('modeSvg',name);glyph.setProperty('modeSize',22);glyph.setPixmap(mode_pixmap(name,22));glyph.setAlignment(Qt.AlignCenter);glyph.setAttribute(Qt.WA_TransparentForMouseEvents);inner.addWidget(glyph)
        label=QLabel(name);label.setAlignment(Qt.AlignCenter);label.setObjectName('tileText');label.setAttribute(Qt.WA_TransparentForMouseEvents);inner.addWidget(label)
        tile.setProperty('modeName',name)
        tile.clicked.connect(lambda checked=False,value=value:window.apply('profile',value));row.addWidget(tile,1);window.mode_tiles[value]=tile
    modes.addLayout(row)
    gpu,window.gpu_header=section('GPU Mode','icons8-video-card-32.png',True)
    row=QHBoxLayout();row.setSpacing(7);window.gpu_tiles={}
    for name,filename in [('Auto','icons8-automation-32.png'),('Hybrid','icons8-laptop-32.png'),('NVIDIA GPU Only','icons8-video-card-32.png')]:
        tile=QPushButton();tile.setMinimumHeight(62)
        inner=QVBoxLayout(tile);inner.setContentsMargins(2,8,2,8);inner.setSpacing(5)
        glyph=QLabel();glyph.setProperty('assetPixmap',filename);glyph.setProperty('assetSize',20);glyph.setPixmap(themed_pixmap(filename,20));glyph.setAlignment(Qt.AlignCenter);inner.addWidget(glyph)
        if name=='Hybrid':glyph.setProperty('assetPixmap',None);glyph.setProperty('modeSvg','HybridGpu');glyph.setProperty('modeSize',20);glyph.setPixmap(mode_pixmap('HybridGpu',20))
        label=QLabel(name);label.setAlignment(Qt.AlignCenter);label.setWordWrap(True);label.setObjectName('tileText');inner.addWidget(label)
        tile.setObjectName('modeTile');tile.setCheckable(True)
        for child in (glyph,label):child.setAttribute(Qt.WA_TransparentForMouseEvents)
        tile.setEnabled(False)
        tile.clicked.connect(lambda checked=False,name=name:window.stage_gpu_mode(name))
        row.addWidget(tile,1);window.gpu_tiles[name]=tile
    gpu.addLayout(row)
    display,window.display_header=section('Display','icons8-laptop-32.png')
    row=QHBoxLayout();row.setSpacing(7)
    window.original_auto=action('Auto',height=38);window.original_auto.setCheckable(True);window.original_auto.clicked.connect(lambda checked: window.refresh_auto.setChecked(checked));row.addWidget(window.original_auto,1)
    window.refresh.setMinimumHeight(38);window.refresh.setFixedHeight(38);row.addWidget(window.refresh,2);window.refresh.activated.connect(lambda index:window.apply('display',window.refresh.itemData(index)));display.addLayout(row)
    layout.addSpacing(10)
    footer=QVBoxLayout();footer.setSpacing(6)
    for items in [[('Lighting','icons8-color-32.png','Lighting'),('Overlay','icons8-soonvibes-32.png','Overlay'),('Fans','icons8-fan-32.png','Fans')],
                  [('Tuning','icons8-processor-32.png','Tuning'),('Quit','icons8-quit-32.png','Quit')]]:
        row=QHBoxLayout();row.setSpacing(4)
        for text,filename,target in items:
            b=action(text,filename);b.clicked.connect(window.quit_app if target=='Quit' else lambda checked=False,target=target:show_dialog(window,target));row.addWidget(b,1)
        footer.addLayout(row)
    layout.addLayout(footer)
    window.status.hide()
    window.setCentralWidget(root);window.setFixedWidth(500);window.setMinimumHeight(0);window.adjustSize()
    window.setWindowTitle('PreySense')
    window.setWindowFlags(window.windowFlags()|Qt.FramelessWindowHint)
    window.overlay_dialog=QDialog(window);window.overlay_dialog.setWindowTitle('PreySense • Overlay');window.overlay_dialog.resize(540,380)
    ol=QVBoxLayout(window.overlay_dialog)
    from metrics_overlay import controls as overlay_controls
    overlay_controls(window,ol)
    # Drag the original frameless shell from its title bar through native window moving.
    def press(event):
        if event.button()==Qt.LeftButton and event.position().y()<42:
            handle=window.windowHandle()
            if handle: handle.startSystemMove()
    root.mousePressEvent=press
    finish_control_windows(window)
    from lighting_ui import build_lighting_window
    window.dialogs['Lighting']=build_lighting_window(window)
    from platform_windows import build_platform_windows
    platform=build_platform_windows(window)
    window.dialogs['System'].hide()
    window.dialogs.pop('System',None)
    window.dialogs['Settings']=platform['settings']
    from slider_snap import configure_snap
    configure_snap(window.original_timeout,10,30)
    configure_snap(window.tau_slider.slider,1)
    for slider in window.dialogs['Fans'].findChildren(QSlider):configure_snap(slider,1)


def show_dialog(window,name):
    dialog=window.overlay_dialog if name=='Overlay' else window.dialogs[name]
    dialog.show();dialog.raise_();dialog.activateWindow()

def update(window,data):
    if not hasattr(window,'mode_tiles'):return
    for value,tile in window.mode_tiles.items():
        tile.setChecked(value==getattr(window,'_profile_preview',None) if getattr(window,'_profile_preview',None) is not None else str(value)==data.get('profile'));tile.setEnabled(window.mode_apply.isEnabled())
    gpu_state=data.get('gpu_mode') or {}
    firmware=gpu_state.get('firmware')
    window._gpu_firmware_mode=firmware
    for name,tile in window.gpu_tiles.items():
        tile.setChecked(name==firmware)
        tile.setEnabled(gpu_state.get('writable',False) and
                        (name!='NVIDIA GPU Only' or gpu_state.get('discrete_available',False)))
    if hasattr(window,'display_header') and window.display_header: window.display_header.setText("")
    # MainWindow headers: CPU/GPU temp · RPM while visible (Windows MainWindow.xaml).
    if hasattr(window,'cpu_header') and window.cpu_header:
        if window.isVisible() and data.get('telemetry_sample', True):
            def _temp(key):
                val=data.get(key)
                if val is None or str(val)=='0': return 'N/A'
                return f'{val}°C'
            def _rpm(key):
                val=data.get(key)
                if val is None: return 'N/A'
                try: return f'{int(float(val)/100+.5)*100} RPM'
                except (TypeError, ValueError): return 'N/A'
            window.cpu_header.setText(f"CPU: {_temp('cpu_temp')} · {_rpm('cpu_fan')}")
            window.gpu_header.setText(f"GPU: {_temp('gpu_temp')} · {_rpm('gpu_fan')}")
        elif not window.isVisible():
            window.cpu_header.setText('CPU: N/A · N/A')
            window.gpu_header.setText('GPU: N/A · N/A')
    if hasattr(window, 'fan_cpu_temp_reading') and hasattr(window, 'fan_gpu_temp_reading'):
        fans_dlg = getattr(window, 'dialogs', {}).get('Fans')
        if fans_dlg and fans_dlg.isVisible() and data.get('telemetry_sample', True):
            cpu_t = data.get('cpu_temp')
            cpu_r = data.get('cpu_fan')
            gpu_t = data.get('gpu_temp')
            gpu_r = data.get('gpu_fan')
            window.fan_cpu_temp_reading.setText(f"{cpu_t}°C" if cpu_t is not None and str(cpu_t) != '0' else "—")
            window.fan_cpu_fan_reading.setText(f"{int(float(cpu_r)/100+.5)*100} RPM" if cpu_r is not None else "—")
            window.fan_gpu_temp_reading.setText(f"{gpu_t}°C" if gpu_t is not None and str(gpu_t) != '0' else "—")
            window.fan_gpu_fan_reading.setText(f"{int(float(gpu_r)/100+.5)*100} RPM" if gpu_r is not None else "—")
        elif fans_dlg and not fans_dlg.isVisible():
            window.fan_cpu_temp_reading.setText("—")
            window.fan_cpu_fan_reading.setText("—")
            window.fan_gpu_temp_reading.setText("—")
            window.fan_gpu_fan_reading.setText("—")
    if not window.profile_editors_initialized and hasattr(window,'saved_fan_policies'):
        try:current=int(data.get('profile') or 1)
        except ValueError:current=1
        for combo in (window.fan_profile,window.power_profile):
            combo.blockSignals(True)
            index=combo.findData(current)
            if index>=0:combo.setCurrentIndex(index)
            combo.blockSignals(False)
        window.load_fan_policy();window.load_power_policy();window.profile_editors_initialized=True
    elif hasattr(window,'power_profile') and not window.power_profile.hasFocus():
        try:current=int(data.get('profile') or 1)
        except ValueError:current=1
        if window.power_profile.currentData() != current:
            idx = window.power_profile.findData(current)
            if idx >= 0:
                window.power_profile.blockSignals(True)
                window.power_profile.setCurrentIndex(idx)
                window.power_profile.blockSignals(False)
                window.load_power_policy()
    window.original_auto.setChecked(window.refresh_auto.isChecked());window.original_auto.setEnabled(window.refresh_auto.isEnabled())
    display=data.get('display')
    current=next((m for m in display['modes'] if m['id']==display['current']),None) if display else None
    if hasattr(window,'original_timeout') and not window.original_timeout_initialized and data.get('led_timeout') is not None:
        try:
            val = int(data['led_timeout'])
            window.original_timeout.setValue(val if 0 <= val <= 120 else 30)
        except ValueError:
            window.original_timeout.setValue(30)
        window.original_timeout_initialized=True
    # Keep display headers clean matching WPF
    pass

STYLE='''
QWidget { background:#1c1c1c; color:#f0f0f0; font-size:12px; }
QWidget#shell { border:1px solid #1c1c1c; border-radius:8px; }
QDialog[preysenseShell="true"] { border:1px solid #1c1c1c; border-radius:8px; }
QWidget#preysenseTitleBar { background:transparent; }
QLabel#windowBrand,QLabel#windowSubtitle { font-size:12px; font-weight:600; }
QLabel#sectionTitle { font-size:13px; font-weight:600; }
QLabel[settingLabel="true"] { font-weight:600; }
QPushButton#windowCloseButton { background:transparent; border:none; border-top-right-radius:7px; border-top-left-radius:0; border-bottom-left-radius:0; border-bottom-right-radius:0; padding:0; }
QPushButton#windowCloseButton:hover { background:#c42b1c; color:#ffffff; }
QPushButton#windowCloseButton:pressed { background:#a62519; color:#ffffff; }

QPushButton,QComboBox { background:#2e2e2e; border:1px solid #424242; border-radius:4px; padding:0 7px; }
QPushButton:hover { background:#383838; border-color:#545454; }
QPushButton:pressed { background:#242424; }
QPushButton:checked { background:#2e2e2e; border:2px solid #3aaeef; }
QPushButton[modeName="Eco"]:checked { border-color:#06b48a; }
QPushButton[modeName="Quiet"]:checked { border-color:#d2d2d2; }
QPushButton[modeName="Performance"]:checked { border-color:#9333ea; }
QPushButton[modeName="Turbo"]:checked { border-color:#ff2020; }
QPushButton:disabled,QComboBox:disabled { color:#787878; background:#242424; border-color:#333333; }
QPushButton#modeTile { padding:0; } QLabel#tileText { background:transparent; font-size:11px; }
QLabel { background:transparent; } QLabel:disabled { color:#787878; } QLabel#sensor { font-size:11px; }
QPushButton#titleButton { background:transparent; border:none; color:#a8a8a8; font-size:16px; font-weight:bold; padding:0; border-radius:4px; }
QPushButton#titleButton:hover { background:#383838; color:#f0f0f0; }
QPushButton#titleButton:pressed { background:#242424; }
QPushButton#titleButton[text="×"]:hover, QPushButton#titleButton[text="✕"]:hover { background:#e81123; color:#ffffff; }
QPushButton#titleButton[text="×"]:pressed, QPushButton#titleButton[text="✕"]:pressed { background:#f1707a; color:#ffffff; }
QLabel#status { color:#a8a8a8; font-size:10px; }
QFrame[preysenseSeparator="true"] { background:#373737; border:none; }
QDialog { background:#1c1c1c; }
QGroupBox { border:1px solid #373737; border-radius:6px; margin-top:12px; padding:12px; }
QGroupBox::title { subcontrol-origin:margin; left:12px; }
QLineEdit,QSpinBox,QDoubleSpinBox,QPlainTextEdit { background:#2e2e2e; border:1px solid #424242; border-radius:4px; padding:0 8px; min-height:26px; height:26px; color:#f0f0f0; }
QLineEdit:hover,QSpinBox:hover,QDoubleSpinBox:hover { background:#383838; border-color:#545454; }
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus { background:#2e2e2e; border:1px solid #3aaeef; }
QLineEdit:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled { color:#787878; background:#242424; border-color:#333333; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0px; height:0px; border:none; }
QComboBox { min-height:26px; height:26px; padding:0 10px; background:#2e2e2e; border:1px solid #424242; border-radius:4px; }
QComboBox:hover { background:#383838; border-color:#545454; }
QComboBox:focus { border:1px solid #3aaeef; }
QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:22px; border:none; }
QComboBox::down-arrow { image:url(__CHEVRON__); width:8px; height:5px; border:none; }

QSlider:horizontal { min-height:24px; padding:0 2px; }
QSlider::groove:horizontal { height:5px; background:#282b32; border-radius:2px; }
QSlider::sub-page:horizontal { background:#4a5260; border-radius:2px; }
QSlider::handle:horizontal { width:12px; height:12px; margin:-5px 0 -6px 0; background:#5c6576; border:2px solid #eaeff5; border-radius:8px; }
QSlider::handle:horizontal:hover { background:#758197; border:2px solid #ffffff; }
QSlider::handle:horizontal:pressed { background:#8b97af; border:2px solid #ffffff; }
QScrollArea { border:none; }
QScrollBar:vertical { background:transparent; width:5px; margin:0; }
QScrollBar::handle:vertical { background:#758197; min-height:24px; border-radius:2px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QHeaderView::section { background:#242424; color:#a8a8a8; border:1px solid #373737; padding:7px; }
QTableWidget { border:1px solid #373737; gridline-color:#373737; }
'''.replace('__CHEVRON__',str(Path(__file__).parent/'assets/chevron-dark.svg'))

def finish_control_windows(window):
    """Retain the original Lighting wheel and Fans graph rather than a generic form."""
    from PySide6.QtWidgets import QCheckBox,QLineEdit,QSlider
    from controls import ColorWheel,FanGraph
    from fan_curve import (
        default_request_stages, build_graph, apply_entry_temperatures, set_stage_duty,
        estimated_rpm, duty_bounds, temperature_bounds,
    )
    from ui_controls import SettingValueRow, SettingSliderRow
    def dialog(name,width):
        old=window.dialogs[name];old.hide()
        d=QDialog(window);d.setWindowTitle('PreySense • '+('Advanced' if name=='System' else name));d.setFixedWidth(width);d.setWindowFlags(d.windowFlags()|Qt.FramelessWindowHint)
        root=QVBoxLayout(d);root.setContentsMargins(0,0,0,0);root.setSpacing(0)
        from window_chrome import WindowTitleBar
        root.addWidget(WindowTitleBar(d,'Advanced' if name=='System' else name))
        content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(14,10,14,8);body.setSpacing(12);root.addWidget(content)
        window.dialogs[name]=d
        return d,body
    def labeled(body,title,widget):
        row=QHBoxLayout();label=QLabel(title);label.setProperty('settingLabel',True);row.addWidget(label);row.addStretch();row.addWidget(widget);body.addLayout(row)
    lighting,l=dialog('Lighting',500)
    brightness_value=QLabel(f'{window.brightness.value()}%');labeled(l,'☀  Brightness',brightness_value);window.brightness.valueChanged.connect(lambda v:brightness_value.setText(f'{v}%'));l.addWidget(window.brightness)
    timeout_value=QLabel('30 s');labeled(l,'Backlight Timeout',timeout_value)
    timeout=QSlider(Qt.Horizontal);timeout.setRange(0,120);timeout.setSingleStep(10);timeout.setPageStep(30);timeout.setValue(30)
    timeout.valueChanged.connect(lambda v:timeout_value.setText('OFF' if not v else f'{v} s'))
    timeout.sliderReleased.connect(lambda:window.apply('led_timeout',timeout.value()))
    l.addWidget(timeout)
    target=QHBoxLayout();keyboard=action('Keyboard','icons8-edit-32.png');keyboard.setCheckable(True);keyboard.setChecked(True);target.addWidget(keyboard);logo=action('Logo','icons8-laptop-32.png');logo.setCheckable(True);target.addWidget(logo);l.addLayout(target)
    engine=QComboBox();engine.addItems(['Hardware','Software']);labeled(l,'Lighting Engine',engine)
    labeled(l,'Lighting Mode',window.effect)
    sync=QCheckBox();sync.setChecked(True);labeled(l,'Sync All Zones',sync)
    zonebox=QWidget();zones=QHBoxLayout(zonebox);zones.setContentsMargins(0,0,0,0)
    selected=[0]
    for i,b in enumerate(window.color_buttons):
        b.clicked.disconnect();b.setMinimumHeight(32);b.setMaximumHeight(32);b.setStyleSheet(b.styleSheet().replace("min-height:64px","min-height:32px"));b.clicked.connect(lambda checked=False,i=i:select(i));zones.addWidget(b)
    zonebox.hide();sync.toggled.connect(lambda checked:zonebox.setVisible(not checked));l.addWidget(zonebox)
    wheel=ColorWheel();wheel.color=window.colors[0];l.addWidget(wheel,0,Qt.AlignHCenter)
    colorrow=QHBoxLayout();colorrow.addStretch();colorrow.addWidget(QLabel('Color:'));hexedit=QLineEdit(wheel.color.name().upper());hexedit.setMaximumWidth(100);colorrow.addWidget(hexedit);colorrow.addStretch();l.addLayout(colorrow)
    def select(i):
        selected[0]=i;wheel.color=window.colors[i];wheel.update();hexedit.setText(wheel.color.name().upper())
    def changed(color):
        if sync.isChecked():window.colors=[QColor(color) for _ in range(4)]
        else:window.colors[selected[0]]=QColor(color)
        wheel.color=QColor(color);wheel.update();hexedit.setText(color.name().upper());window.paint_colors()
        for b in window.color_buttons:b.setStyleSheet(b.styleSheet().replace('min-height:64px','min-height:32px'))
    wheel.changed.connect(changed)
    def hex_commit():
        c=QColor(hexedit.text())
        if c.isValid():changed(c)
        else:hexedit.setText(wheel.color.name().upper())
    hexedit.editingFinished.connect(hex_commit)
    labeled(l,'Animation Speed',window.speed)
    window.rgb_apply.setMinimumHeight(34);l.addWidget(window.rgb_apply)
    from hardware import EFFECTS
    from lighting_effects import SOFTWARE_EFFECTS
    window.lighting_target='Keyboard';window.sync_logo=window.settings.value('sync_logo',False,type=bool)
    saved_effect=window.effect.currentText()
    target_states={'Keyboard':dict(colors=list(window.colors),brightness=window.brightness.value(),effect=saved_effect,speed=window.speed.value()),
                   'Logo':dict(colors=[QColor(window.settings.value('logo_color','#00AEC7'))]*4,brightness=int(window.settings.value('logo_brightness',100)),effect=window.settings.value('logo_effect','Mode'),speed=int(window.settings.value('logo_speed',5))),
                   'ModeKey':dict(colors=[QColor(window.settings.value('mode_key_color','#00AEC7'))]*4,brightness=int(window.settings.value('mode_key_brightness',100)),effect=window.settings.value('mode_key_effect','Mode'),speed=int(window.settings.value('mode_key_speed',5)))}
    window.lighting_target_states=target_states
    sync_logo=QCheckBox('Sync cover logo with keyboard');window.sync_logo_checkbox=sync_logo;sync_logo.setChecked(window.sync_logo);l.addWidget(sync_logo)
    sync_logo.toggled.connect(lambda enabled:(setattr(window,'sync_logo',enabled),window.settings.setValue('sync_logo',enabled)))
    def choose_engine(_=None,desired=None):
        current=desired or window.effect.currentText();window.effect.blockSignals(True);window.effect.clear()
        if window.lighting_target=='Logo':window.effect.addItems(['Off','Static','Breathing','Neon'])
        else:window.effect.addItems(list(SOFTWARE_EFFECTS) if engine.currentText()=='Software' else [*EFFECTS,'Mode'])
        index=window.effect.findText(current);window.effect.setCurrentIndex(max(0,index));window.effect.blockSignals(False)
        software=window.lighting_target=='Keyboard' and engine.currentText()=='Software'
        zonebox.setVisible(software or (window.lighting_target=='Keyboard' and not sync.isChecked()));sync.setEnabled(not software and window.lighting_target=='Keyboard')
    engine.currentIndexChanged.connect(choose_engine)
    engine.setCurrentText('Software' if saved_effect in SOFTWARE_EFFECTS else 'Hardware');choose_engine(desired=saved_effect)
    def target_selected(name):
        old=window.lighting_target
        target_states[old]=dict(colors=list(window.colors),brightness=window.brightness.value(),effect=window.effect.currentText(),speed=window.speed.value())
        window.lighting_target=name;state=target_states[name]
        window.colors=list(state['colors']);window.brightness.setValue(state['brightness']);window.speed.setValue(state['speed'])
        keyboard.setChecked(name=='Keyboard');logo.setChecked(name=='Logo');engine.setEnabled(name=='Keyboard');sync_logo.setVisible(name=='Keyboard')
        engine.blockSignals(True);engine.setCurrentText('Software' if state['effect'] in SOFTWARE_EFFECTS else 'Hardware');engine.blockSignals(False)
        choose_engine(desired=state['effect']);select(0);window.paint_colors()
        for b in window.color_buttons:b.setStyleSheet(b.styleSheet().replace('min-height:64px','min-height:32px'))
    keyboard.clicked.connect(lambda:target_selected('Keyboard'));logo.clicked.connect(lambda:target_selected('Logo'))
    def preview(colors):
        if window.lighting_target!='Keyboard' or engine.currentText()!='Software':return
        for button,color in zip(window.color_buttons,colors):button.setStyleSheet(f'background:rgb{tuple(color)};color:#ffffff;min-height:32px;')
    window.worker.lighting_frame.connect(preview)
    lighting.adjustSize()
    # Keep a reference for telemetry to update the timeout without changing user edits.
    window.original_timeout=timeout;window.original_timeout_initialized=False
    fans,f=dialog('Fans',560)
    window.fan_profile=QComboBox()
    for name in ('Eco','Quiet','Balanced','Performance','Turbo'):
        window.fan_profile.addItem(name, MODES[name])
    window.fan_profile.setCurrentText('Balanced');window.fan_profile.setFixedWidth(140);labeled(f,'Profile Mode',window.fan_profile)
    options=QHBoxLayout();options.addWidget(window.fan_auto);options.addWidget(window.fan_max)
    custom=action('Custom');custom.setCheckable(True);options.addWidget(custom);f.addLayout(options)
    window.fan_auto.setText('Auto');window.fan_max.setText('Max')
    window.fan_kind_buttons={'Auto':window.fan_auto,'Max':window.fan_max,'Custom':custom}
    for name,button in window.fan_kind_buttons.items():
        button.setCheckable(True);button.setMinimumHeight(34)
        if name != 'Custom':button.clicked.disconnect()
        button.clicked.connect(lambda checked=False,name=name:(window.set_fan_editor_kind(name),window.apply_fan_policy(True)))
    window.set_fan_editor_kind('Auto')
    channels=QHBoxLayout();cpu=action('CPU Fan','icons8-processor-32.png');gpu=action('GPU Fan','icons8-video-card-32.png');cpu.setCheckable(True);gpu.setCheckable(True);cpu.setChecked(True);channels.addWidget(cpu);channels.addWidget(gpu);f.addLayout(channels)

    # Live telemetry readout banner matching Windows FanCurveWindow.xaml
    fan_telem_widget = QWidget()
    fan_telem_layout = QHBoxLayout(fan_telem_widget)
    fan_telem_layout.setContentsMargins(0, 4, 0, 8)
    cpu_tb = QWidget(); cpu_tb_l = QHBoxLayout(cpu_tb); cpu_tb_l.setContentsMargins(0, 0, 0, 0); cpu_tb_l.setSpacing(4); cpu_tb_l.addStretch()
    window.fan_cpu_temp_reading = QLabel('—'); window.fan_cpu_temp_reading.setStyleSheet('font-weight: 600;')
    dot_c = QLabel('  •  '); dot_c.setObjectName('muted')
    window.fan_cpu_fan_reading = QLabel('—'); window.fan_cpu_fan_reading.setStyleSheet('font-weight: 600;')
    cpu_tb_l.addWidget(window.fan_cpu_temp_reading); cpu_tb_l.addWidget(dot_c); cpu_tb_l.addWidget(window.fan_cpu_fan_reading); cpu_tb_l.addStretch()
    gpu_tb = QWidget(); gpu_tb_l = QHBoxLayout(gpu_tb); gpu_tb_l.setContentsMargins(0, 0, 0, 0); gpu_tb_l.setSpacing(4); gpu_tb_l.addStretch()
    window.fan_gpu_temp_reading = QLabel('—'); window.fan_gpu_temp_reading.setStyleSheet('font-weight: 600;')
    dot_g = QLabel('  •  '); dot_g.setObjectName('muted')
    window.fan_gpu_fan_reading = QLabel('—'); window.fan_gpu_fan_reading.setStyleSheet('font-weight: 600;')
    gpu_tb_l.addWidget(window.fan_gpu_temp_reading); gpu_tb_l.addWidget(dot_g); gpu_tb_l.addWidget(window.fan_gpu_fan_reading); gpu_tb_l.addStretch()
    fan_telem_layout.addWidget(cpu_tb); fan_telem_layout.addWidget(gpu_tb)
    f.addWidget(fan_telem_widget)

    editor=QWidget();editor_layout=QVBoxLayout(editor);editor_layout.setContentsMargins(0,0,0,0);editor_layout.setSpacing(8)
    graph=FanGraph();graph.setFixedHeight(230);editor_layout.addWidget(graph)
    row_temp=SettingValueRow('CPU Temp',40,'°C',40,100)
    row_duty=SettingValueRow('CPU Cooling Boost',0,'%',0,100)
    rpm_readout=QLineEdit('—')
    rpm_readout.setReadOnly(True)
    rpm_readout.setFocusPolicy(Qt.NoFocus)
    rpm_readout.setAlignment(Qt.AlignRight)
    rpm_readout.setFixedWidth(72)
    rpm_readout.setToolTip('Approximate factory reference at the selected temperature')
    rpm_value=QWidget()
    rpm_layout=QHBoxLayout(rpm_value)
    rpm_layout.setContentsMargins(0,0,0,0)
    rpm_layout.setSpacing(6)
    rpm_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
    rpm_layout.addWidget(rpm_readout)
    rpm_layout.addWidget(QLabel('RPM'))
    editor_layout.addWidget(row_temp);editor_layout.addWidget(row_duty)
    labeled(editor_layout,'Estimated RPM',rpm_value)
    f.addWidget(editor)
    window.fan_error=QLabel()
    window.fan_error.setWordWrap(True)
    window.fan_error.hide()
    f.addWidget(window.fan_error)
    window._fan_visible_indices=[];window._fan_loading=False
    def sync_stage_rows():
        visible=graph.index;enabled=window.fan_editor_kind=='Custom' and visible>=0 and visible<len(window._fan_visible_indices)
        for row in (row_temp,row_duty):row.setEnabled(enabled)
        gpu=window.fan_channel_gpu;fan='GPU' if gpu else 'CPU'
        row_temp.label.setText(f'{fan} Temp')
        row_duty.label.setText(f'{fan} Cooling Boost')
        if not enabled:
            rpm_readout.setText('—')
            return
        stage_index=window._fan_visible_indices[visible]
        stage=window.fan_stages[stage_index]
        duty=stage['GpuDutyPercent' if gpu else 'CpuDutyPercent']
        low_d,high_d=duty_bounds(graph.values,visible);low_t,high_t=temperature_bounds(graph.temperatures,visible)
        window._fan_loading=True
        temperature=graph.temperatures[visible]
        row_temp.spin.setRange(low_t,high_t);row_duty.spin.setRange(low_d,high_d)
        row_temp.setValue(temperature);row_duty.setValue(duty)
        rpm=estimated_rpm(window.fan_profile.currentData(),temperature,duty,gpu)
        rpm_readout.setText(f'{rpm:,}')
        window._fan_loading=False
    def refresh_fan_graph(keep_selection=True):
        previous=window._fan_visible_indices[graph.index] if keep_selection and 0<=graph.index<len(window._fan_visible_indices) else -1
        indices,temps,duties,lead=build_graph(window.fan_stages,gpu=window.fan_channel_gpu)
        window._fan_visible_indices=indices
        graph.set_curve(temps,duties,lead)
        if previous in indices:graph.index=indices.index(previous)
        else:graph.index=-1
        sync_stage_rows();graph.update()
    window.refresh_fan_graph=refresh_fan_graph
    def choose_channel(gpu_channel):
        window.fan_channel_gpu=bool(gpu_channel);cpu.setChecked(not gpu_channel);gpu.setChecked(gpu_channel);refresh_fan_graph(False)
    cpu.clicked.connect(lambda:choose_channel(False));gpu.clicked.connect(lambda:choose_channel(True))
    def on_graph_selected(index):
        graph.index=index;sync_stage_rows()
    def on_graph_changed():
        if window._fan_loading or window.fan_editor_kind!='Custom' or graph.index<0:return
        visible=graph.index;stage_index=window._fan_visible_indices[visible]
        window.fan_stages=apply_entry_temperatures(window.fan_stages,window._fan_visible_indices,graph.temperatures,window.fan_channel_gpu)
        window.fan_stages=set_stage_duty(window.fan_stages,stage_index,graph.values[visible],window.fan_channel_gpu)
        refresh_fan_graph()
    graph.selected.connect(on_graph_selected);graph.changed.connect(on_graph_changed)
    def commit_stage_field(sender):
        if window._fan_loading or window.fan_editor_kind!='Custom' or graph.index<0:return
        visible=graph.index;stage_index=window._fan_visible_indices[visible]
        gpu_channel=window.fan_channel_gpu
        if sender is row_temp:
            temps=list(graph.temperatures);temps[visible]=row_temp.value()
            window.fan_stages=apply_entry_temperatures(window.fan_stages,window._fan_visible_indices,temps,gpu_channel)
        else:
            window.fan_stages=set_stage_duty(window.fan_stages,stage_index,row_duty.value(),gpu_channel)
        refresh_fan_graph()
    row_temp.valueChanged.connect(lambda *_:commit_stage_field(row_temp))
    row_duty.valueChanged.connect(lambda *_:commit_stage_field(row_duty))
    footer=QHBoxLayout();reset=action('Reset');save=action('Save')
    drafts={}
    editor_mode=str(window.fan_profile.currentData())
    def reset_curve():
        mode=window.fan_profile.currentData()
        window.fan_stages=default_request_stages(mode)
        window.curve_delay.setValue(0)
        refresh_fan_graph(False)
        drafts.pop(str(mode),None)
        window.apply_fan_policy(True)
    def select_fan_profile():
        nonlocal editor_mode
        drafts[editor_mode]=window.fan_editor_policy()
        editor_mode=str(window.fan_profile.currentData())
        window.load_fan_policy(drafts.get(editor_mode))
        refresh_fan_graph(False)
    def save_fan_profiles():
        window.apply_fan_policy(True,drafts=drafts)
        drafts.clear()
    reset.clicked.connect(reset_curve)
    save.clicked.connect(save_fan_profiles)
    window.fan_profile.currentIndexChanged.connect(select_fan_profile)
    footer.addWidget(reset);footer.addWidget(save);footer.setContentsMargins(14,10,14,16);footer.setSpacing(4);fan_footer=QWidget();fan_footer.setLayout(footer);fans.layout().addWidget(fan_footer)
    def fan_editor_state(kind,buttons=(reset,save),panel=fan_footer):
        enabled=kind=='Custom'
        editor.setEnabled(enabled);panel.setVisible(enabled)
        for widget in buttons:widget.setVisible(enabled)
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        effect=editor.graphicsEffect()
        if effect is None:effect=QGraphicsOpacityEffect(editor);editor.setGraphicsEffect(effect)
        effect.setOpacity(1 if enabled else .45)
        sync_stage_rows();fans.adjustSize()
    window.fan_editor_state=fan_editor_state
    refresh_fan_graph(False);fan_editor_state(window.fan_editor_kind);fans.adjustSize()

    def on_fan_show(event):
        nonlocal editor_mode
        editor_mode=str(window.fan_profile.currentData())
        QDialog.showEvent(fans, event)
        if hasattr(window, 'command'):
            window.command.emit('fan_window_visible', True)
    def on_fan_hide(event):
        if hasattr(window, 'command'):
            window.command.emit('fan_window_visible', False)
        QDialog.hideEvent(fans, event)
    fans.showEvent = on_fan_show
    fans.hideEvent = on_fan_hide

    # Match PreySense.Frontend/Views/ModeSettingsWindow.xaml structure.
    from ui_controls import SettingSwitchRow, SettingSliderRow, SettingValueRow, SettingDropdownRow, RectangularSwitch
    from gpu_offsets import GpuOffsets
    from slider_snap import configure_snap
    from PySide6.QtWidgets import QScrollArea, QFrame
    tuning,t=dialog('Tuning',500)
    t.setSpacing(8)

    gated=QWidget(); gated_l=QVBoxLayout(gated); gated_l.setContentsMargins(0,0,0,0); gated_l.setSpacing(8)
    window.tuning_controls=gated

    mode_row=SettingDropdownRow('Performance Mode', dropdown_width=140)
    for name in ('Eco','Quiet','Balanced','Performance','Turbo'):
        mode_row.addItem(name, MODES[name])
    mode_row.setCurrentText('Balanced')
    window.power_profile=mode_row.combo
    gated_l.addWidget(mode_row)

    body=QWidget(); body_l=QVBoxLayout(body); body_l.setContentsMargins(0,0,0,0); body_l.setSpacing(8)
    class TuningScroll(QScrollArea):
        def sizeHint(self):
            size = super().sizeHint()
            size.setHeight(min(430, body.sizeHint().height()))
            return size

    scroll = TuningScroll()
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(body)
    scroll.setMaximumHeight(430)
    gated_l.addWidget(scroll)

    def section(title, icon_name):
        head=QWidget(); hl=QHBoxLayout(head); hl.setContentsMargins(0,4,0,4)
        icon_lab=QLabel(); icon_lab.setPixmap(icon(icon_name).pixmap(14,14)); hl.addWidget(icon_lab)
        title_lab=QLabel(title); title_lab.setObjectName('sectionTitle'); hl.addWidget(title_lab); hl.addStretch()
        sw=RectangularSwitch(); hl.addWidget(sw)
        panel=QWidget(); pl=QVBoxLayout(panel); pl.setContentsMargins(0,0,0,0); pl.setSpacing(4)
        wrap=QWidget(); wl=QVBoxLayout(wrap); wl.setContentsMargins(0,0,0,8); wl.setSpacing(0)
        wl.addWidget(head); wl.addWidget(panel)
        return wrap, panel, pl, sw

    window.cpu_boost = SettingSwitchRow('CPU Boost', checked=True)
    body_l.addWidget(window.cpu_boost)

    cpu_wrap, cpu_panel, cpu_l, window.apply_cpu_switch = section('CPU Power Limits','icons8-processor-32.png')
    window.apply_cpu_switch.setChecked(False)
    window.power_pl1.setRange(5,300); window.power_pl2.setRange(5,300)
    pl1_row=SettingValueRow('Sustained Long Power [PL1]', window.power_pl1.value(), 'W', 5, 300)
    pl2_row=SettingValueRow('Burst Peak Power [PL2]', window.power_pl2.value(), 'W', 5, 300)
    pl1_row.valueChanged.connect(window.power_pl1.setValue); window.power_pl1.valueChanged.connect(pl1_row.setValue)
    pl2_row.valueChanged.connect(window.power_pl2.setValue); window.power_pl2.valueChanged.connect(pl2_row.setValue)
    window.power_pl1_row=pl1_row; window.power_pl2_row=pl2_row
    cpu_l.addWidget(pl1_row); cpu_l.addWidget(pl2_row)
    window.power_tau=QComboBox()
    tau_steps=(0,1,2,4,8,16,32,56,64,128,256,449)
    for value in tau_steps: window.power_tau.addItem('Off' if value==0 else '∞' if value==449 else f'{value} s', value)
    window.power_tau.setCurrentIndex(window.power_tau.findData(56))
    tau_slider=SettingSliderRow('Turbo Time Limit [Tau]', 0, 11, max(0, window.power_tau.currentIndex()), unit='')
    window.tau_slider=tau_slider
    def on_tau_slide(idx):
        if 0 <= idx < len(tau_steps):
            val=tau_steps[idx]
            tau_slider.label_value.setText('Off' if val==0 else '∞' if val==449 else f'{val} s')
            window.power_tau.setCurrentIndex(idx)
    tau_slider.valueChanged.connect(on_tau_slide); on_tau_slide(tau_slider.value())
    cpu_l.addWidget(tau_slider)
    window.apply_cpu_switch.toggled.connect(lambda on: cpu_panel.setEnabled(on))
    cpu_panel.setEnabled(False)
    body_l.addWidget(cpu_wrap)

    class _SliderValue:
        def __init__(self, row): self._row=row
        def value(self): return int(self._row.value())
        def setValue(self, v):
            self._row.slider.blockSignals(True); self._row.setValue(int(v)); self._row.slider.blockSignals(False)
            self._row.label_value.setText(f'{int(v)}{self._row._unit}')
        def setEnabled(self, enabled): self._row.setEnabled(enabled)

    gpu=GpuOffsets(); window.gpu_offsets_available=gpu.available
    gpu_wrap, gpu_panel, gpu_l, window.apply_gpu_switch = section('GPU Power Limits','icons8-video-card-32.png')
    window.apply_gpu_switch.setChecked(False); window.apply_gpu_switch.setEnabled(gpu.available)
    window.gpu_power_row=SettingValueRow('Power Limit', 0, 'W', 0, 400)
    window.gpu_power_row.setEnabled(False)
    window.gpu_power_row.spin.setSpecialValueText('N/A')
    gpu_l.addWidget(window.gpu_power_row)
    window.gpu_ct_slider=SettingSliderRow('Delta', 0, 255, 0, unit=' W')
    window.gpu_db_slider=SettingSliderRow('Dynamic Boost', 0, 25, 0, unit=' W')
    window.gpu_cp_slider=SettingSliderRow('Platform Power Limit Offset', 0, 255, 0, unit=' W')
    for slider in (window.gpu_ct_slider, window.gpu_db_slider, window.gpu_cp_slider):
        configure_snap(slider.slider, 5)
        gpu_l.addWidget(slider)
    window.gpu_ct=_SliderValue(window.gpu_ct_slider)
    window.gpu_db=_SliderValue(window.gpu_db_slider)
    window.gpu_cp=_SliderValue(window.gpu_cp_slider)
    def refresh_gpu_nominal():
        base=getattr(window,'_gpu_base_watts', None)
        if base is None:
            # Query from settings / config_store or NVML
            val = window.settings.value('gpu_base_watts', None) if hasattr(window, 'settings') else None
            if val is not None:
                try: base = int(val)
                except (ValueError, TypeError): base = None
            if base is None:
                try:
                    from nvml_telemetry import NvmlTelemetry
                    nvml = NvmlTelemetry.get_instance()
                    if nvml.available:
                        m = nvml.read_metrics({'default_power_limit_w'})
                        if m and m.get('default_power_limit_w'):
                            base = int(round(float(m['default_power_limit_w'])))
                            if hasattr(window, 'settings'):
                                window.settings.setValue('gpu_base_watts', base)
                except Exception:
                    pass
            if base is not None:
                window._gpu_base_watts = base
        if base is None:
            window.gpu_power_row.spin.blockSignals(True)
            window.gpu_power_row.spin.setValue(window.gpu_power_row.spin.minimum())
            window.gpu_power_row.spin.blockSignals(False)
            return
        window.gpu_power_row.setValue(int(base)+window.gpu_ct.value()+window.gpu_db.value())
    for slider in (window.gpu_ct_slider, window.gpu_db_slider):
        slider.valueChanged.connect(lambda *_: refresh_gpu_nominal())
    window.refresh_gpu_nominal=refresh_gpu_nominal
    refresh_gpu_nominal()
    window.apply_gpu_switch.toggled.connect(lambda on: gpu_panel.setEnabled(on and gpu.available))
    gpu_panel.setEnabled(False)
    body_l.addWidget(gpu_wrap)
    body_l.addStretch()

    window.power_apply.setText('Apply'); window.power_apply.setMinimumHeight(34)
    try: window.power_apply.clicked.disconnect()
    except TypeError: pass
    window.power_apply.clicked.connect(lambda: window.apply_power_policy(False))

    tuning_status = QLabel('')
    tuning_status.setAlignment(Qt.AlignCenter)
    tuning_status.setWordWrap(True)
    tuning_status.hide()
    window.tuning_status = tuning_status
    gated_l.addWidget(tuning_status)

    footer=QHBoxLayout(); reset=action('Reset'); reset.clicked.connect(window.reset_power_policy)
    footer.addWidget(reset); footer.addWidget(window.power_apply)
    save=action('Save'); window.power_save=save; save.clicked.connect(lambda: window.apply_power_policy(True))
    footer.addWidget(save); footer.setContentsMargins(0,8,0,0); footer.setSpacing(4)
    tuning_footer=QWidget(); tuning_footer.setLayout(footer); gated_l.addWidget(tuning_footer)
    t.addWidget(gated)

    def refresh_tuning_master_switches():
        enable_cpu_limits = bool(window.settings.value('enable_cpu_power_limits', True, type=bool))
        enable_gpu_limits = bool(window.settings.value('enable_gpu_power_limits', True, type=bool))

        cpu_wrap.setVisible(enable_cpu_limits)
        gpu_wrap.setVisible(enable_gpu_limits)
        scroll.updateGeometry()
        tuning.adjustSize()
    window.refresh_tuning_master_switches = refresh_tuning_master_switches
    refresh_tuning_master_switches()

    from tuning_settings import build_tuning_settings_dialog
    window.dialogs['TuningSettings'] = build_tuning_settings_dialog(window)

    drafts = {}
    selected_mode = window.power_profile.currentData()

    def select_tuning_profile(_index):
        nonlocal selected_mode
        drafts[selected_mode] = (
            window.cpu_boost.isChecked(),
            window.apply_cpu_switch.isChecked(), window.power_pl1.value(),
            window.power_pl2.value(), window.tau_slider.value(),
            window.apply_gpu_switch.isChecked(), window.gpu_ct.value(),
            window.gpu_db.value(), window.gpu_cp.value(),
        )
        selected_mode = window.power_profile.currentData()
        if selected_mode not in drafts:
            window.load_power_policy()
            return
        boost, cpu_on, pl1, pl2, tau, gpu_on, delta, db, offset = drafts[selected_mode]
        window.cpu_boost.setChecked(boost)
        window.apply_cpu_switch.setChecked(cpu_on)
        window.power_pl1.setValue(pl1)
        window.power_pl2.setValue(pl2)
        window.tau_slider.setValue(tau)
        window.apply_gpu_switch.setChecked(gpu_on)
        window.gpu_ct.setValue(delta)
        window.gpu_db.setValue(db)
        window.gpu_cp.setValue(offset)
        refresh_gpu_nominal()

    window.power_profile.currentIndexChanged.connect(select_tuning_profile)
    tuning.adjustSize()
    def sync_tuning_on_show(event):
        nonlocal selected_mode
        drafts.clear()
        current = getattr(window, '_confirmed_profile', None)
        index = window.power_profile.findData(current)
        if index >= 0:
            window.power_profile.blockSignals(True)
            window.power_profile.setCurrentIndex(index)
            window.power_profile.blockSignals(False)
        selected_mode = window.power_profile.currentData()
        window.load_power_policy()
        QDialog.showEvent(tuning,event)
        tuning.resize(tuning.width(), tuning.sizeHint().height())
    tuning.showEvent=sync_tuning_on_show
    window.profile_editors_initialized=False
