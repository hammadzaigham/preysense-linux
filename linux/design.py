"""Qt rendering of the existing PreySense WPF shell, tokens, icons and navigation."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QDialog,QComboBox,QApplication,QSlider
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
    window.setWindowFlags(window.windowFlags()|Qt.FramelessWindowHint|Qt.NoDropShadowWindowHint)
    window.overlay_dialog=QDialog(window);window.overlay_dialog.setWindowTitle('PreySense • Metrics');window.overlay_dialog.resize(540,380)
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
    configure_snap(window.brightness,25)
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
    # Clean headers matching original WPF MainWindow.xaml (no embedded telemetry or boot status)
    if hasattr(window,'cpu_header') and window.cpu_header: window.cpu_header.setText("")
    if hasattr(window,'gpu_header') and window.gpu_header: window.gpu_header.setText("")
    if hasattr(window,'display_header') and window.display_header: window.display_header.setText("")
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
QWidget#shell { border:1px solid #373737; border-radius:8px; }
QDialog[preysenseShell="true"] { border:1px solid #373737; border-radius:8px; }
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
    from PySide6.QtWidgets import QCheckBox,QLineEdit,QSlider,QStackedWidget,QSpinBox
    from controls import ColorWheel,FanGraph
    from fan_curve import DEFAULT_DUTIES,TEMPERATURES,default_curve
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
                   'Logo':dict(colors=[QColor(window.settings.value('logo_color','#28d8ca'))]*4,brightness=int(window.settings.value('logo_brightness',80)),effect=window.settings.value('logo_effect','Static'),speed=int(window.settings.value('logo_speed',5)))}
    window.lighting_target_states=target_states
    sync_logo=QCheckBox('Sync cover logo with keyboard');window.sync_logo_checkbox=sync_logo;sync_logo.setChecked(window.sync_logo);l.addWidget(sync_logo)
    sync_logo.toggled.connect(lambda enabled:(setattr(window,'sync_logo',enabled),window.settings.setValue('sync_logo',enabled)))
    def choose_engine(_=None,desired=None):
        current=desired or window.effect.currentText();window.effect.blockSignals(True);window.effect.clear()
        if window.lighting_target=='Logo':window.effect.addItems(['Off','Static','Breathing','Neon'])
        else:window.effect.addItems(list(SOFTWARE_EFFECTS) if engine.currentText()=='Software' else list(EFFECTS))
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
    fans,f=dialog('Fans',540)
    window.fan_profile=QComboBox()
    for name,value in MODES.items():window.fan_profile.addItem(name,value)
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
    graphs=QStackedWidget();fan_graphs=[FanGraph(spins) for spins in window.curve_spins]
    for graph in fan_graphs:
        graph.setFixedHeight(300);graph.index=-1;graphs.addWidget(graph)
    f.addWidget(graphs)
    point=QSpinBox();point.setRange(0,100);point.setSingleStep(5);point.setSuffix(' %');point_label=QLabel('Selected Point');pointrow=QHBoxLayout();pointrow.addWidget(point_label);pointrow.addStretch();pointrow.addWidget(point);f.addLayout(pointrow)
    def selected_point(index):
        graph=fan_graphs[graphs.currentIndex()];graph.index=index
        point.blockSignals(True)
        point.setValue(graph.spins[index].value() if index>=0 else 0)
        point.blockSignals(False)
        point.setEnabled(window.fan_editor_kind=='Custom' and index>=0)
        point_label.setText(f'{TEMPERATURES[index]}°C' if index>=0 else 'Selected Point')
    def choose_channel(index):
        graphs.setCurrentIndex(index);cpu.setChecked(index==0);gpu.setChecked(index==1);selected_point(fan_graphs[index].index)
    cpu.clicked.connect(lambda:choose_channel(0));gpu.clicked.connect(lambda:choose_channel(1))
    for graph in fan_graphs:
        graph.selected.connect(selected_point);graph.changed.connect(lambda i,v:selected_point(i))
    def commit_point(value):
        graph=fan_graphs[graphs.currentIndex()];i=graph.index;low=graph.spins[i-1].value() if i else 0;high=graph.spins[i+1].value() if i+1<len(graph.spins) else 100
        if i<0:return
        value=max(low,min(high,value));graph.spins[i].setValue(value);selected_point(i);graph.update()
    point.valueChanged.connect(commit_point);selected_point(-1)
    delay_label=QLabel(f'{window.curve_delay.value():g} s');labeled(f,'Fan Control Delay',delay_label)
    delay=QSlider(Qt.Horizontal);delay.setRange(0,5);delay.setValue(int(window.curve_delay.value()));delay.valueChanged.connect(lambda v:(window.curve_delay.setValue(v),delay_label.setText(f'{v} s')));window.curve_delay.valueChanged.connect(lambda v:delay.setValue(int(v)));f.addWidget(delay)
    footer=QHBoxLayout();reset=action('Reset');apply=window.curve_apply;apply.setText('Apply');apply.setMinimumHeight(34);save=action('Save')
    def reset_curve():
        try:mode=int(window.fan_profile.currentData())
        except (ValueError,TypeError):mode=1
        for channel,spins in enumerate(window.curve_spins):
            defaults=default_curve(mode,gpu=bool(channel))
            for spin,value in zip(spins,defaults):spin.setValue(value)
        selected_point(-1)
    reset.clicked.connect(reset_curve)
    apply.clicked.disconnect();apply.clicked.connect(lambda:window.apply_fan_policy(False));save.clicked.connect(lambda:window.apply_fan_policy(True))
    window.fan_profile.currentIndexChanged.connect(lambda:(window.load_fan_policy(),selected_point(-1)))
    footer.addWidget(reset);footer.addWidget(apply);footer.addWidget(save);footer.setContentsMargins(14,10,14,16);footer.setSpacing(4);fan_footer=QWidget();fan_footer.setLayout(footer);fans.layout().addWidget(fan_footer)
    def fan_editor_state(kind,buttons=(reset,apply,save),panel=fan_footer):
        enabled=kind=='Custom'
        for widget in (graphs,delay):widget.setEnabled(enabled)
        point.setEnabled(enabled and fan_graphs[graphs.currentIndex()].index>=0)
        panel.setVisible(enabled)
        for widget in buttons:widget.setVisible(enabled)
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        effect=graphs.graphicsEffect()
        if effect is None:effect=QGraphicsOpacityEffect(graphs);graphs.setGraphicsEffect(effect)
        effect.setOpacity(1 if enabled else .45)
        fans.adjustSize()
    window.fan_editor_state=fan_editor_state
    fan_editor_state(window.fan_editor_kind)
    fans.adjustSize()

    tuning,t=dialog('Tuning',500)
    window.power_profile=QComboBox()
    for name,value in MODES.items():window.power_profile.addItem(name,value)
    window.power_profile.setCurrentText('Balanced');window.power_profile.setFixedWidth(140);labeled(t,'Profile Mode',window.power_profile)
    window.power_profile.currentIndexChanged.connect(window.load_power_policy)
    window.power_profile.activated.connect(lambda index:window.apply('profile',window.power_profile.itemData(index),immediate=True))
    heading=QLabel('CPU Power Limits');heading.setObjectName('sectionTitle');t.addWidget(heading)
    from ui_controls import SettingSwitchRow, SettingSliderRow
    boost_row = SettingSwitchRow('CPU Boost', checked=True)
    window.cpu_boost = boost_row.switch
    boost_row.toggled.connect(lambda enabled:window.apply_boost_setting(enabled))
    t.addWidget(boost_row)
    for title,spin in [('Sustained Long Power [PL1]',window.power_pl1),('Burst Peak Power [PL2]',window.power_pl2)]:
        spin.setFixedWidth(90);labeled(t,title,spin)
    window.power_tau=QComboBox()
    for value in (0,1,2,4,8,16,32,56,64,128,256,449):window.power_tau.addItem('Off' if value==0 else '∞' if value==449 else f'{value} s',value)
    window.power_tau.setCurrentIndex(window.power_tau.findData(56))
    tau_slider = SettingSliderRow('Burst Window [Tau]', 0, 11, 7, unit='')
    window.tau_slider = tau_slider
    tau_steps = [0,1,2,4,8,16,32,56,64,128,256,449]
    def on_tau_slide(idx):
        if 0 <= idx < len(tau_steps):
            val = tau_steps[idx]
            tau_slider.label_value.setText('Off' if val==0 else '∞' if val==449 else f'{val} s')
            window.power_tau.setCurrentIndex(idx)
    tau_slider.valueChanged.connect(on_tau_slide)
    on_tau_slide(tau_slider.value())
    t.addWidget(tau_slider)
    window.power_apply.setText('Apply');window.power_apply.setMinimumHeight(34);window.power_apply.clicked.disconnect();window.power_apply.clicked.connect(lambda:window.apply_power_policy(False))
    footer=QHBoxLayout();reset=action('Reset');reset.clicked.connect(window.reset_power_policy);footer.addWidget(reset);footer.addWidget(window.power_apply);save=action('Save');window.power_save=save;save.clicked.connect(lambda:window.apply_power_policy(True));footer.addWidget(save);footer.setContentsMargins(14,10,14,16);footer.setSpacing(4);tuning_footer=QWidget();tuning_footer.setLayout(footer);tuning.layout().addWidget(tuning_footer);tuning.adjustSize()
    def sync_tuning_on_show(event):
        try:current=int(getattr(window,'_confirmed_profile',None) or 1)
        except (ValueError,TypeError):current=1
        if window.power_profile.currentData()!=current:
            idx=window.power_profile.findData(current)
            if idx>=0:
                window.power_profile.blockSignals(True)
                window.power_profile.setCurrentIndex(idx)
                window.power_profile.blockSignals(False)
                window.load_power_policy()
        QDialog.showEvent(tuning,event)
    tuning.showEvent=sync_tuning_on_show
    window.profile_editors_initialized=False

    from documentation_ui import DocumentationWindow
    window.documentation=DocumentationWindow(window)
