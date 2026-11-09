#!/usr/bin/env python3
"""PreySense Linux desktop application. Run as the logged-in user, never root."""
import argparse
import os
import json
import sys
import time
import signal
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QObject, QThread, Signal, Slot, QSettings, QLockFile, QStandardPaths
from config_store import ConfigStore, JsonSettings
from PySide6.QtGui import QColor, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSlider, QTabWidget, QGroupBox, QGridLayout,
    QColorDialog, QSystemTrayIcon, QMenu, QCheckBox, QPlainTextEdit, QSpinBox, QDoubleSpinBox)
from hardware import Hardware, MODES, EFFECTS, average_color
from version import __version__
from gpu_mode import GpuMode, requires_confirmation
from system_power import SystemPower
from calibration import Calibrator
from source_profiles import SourceProfiles, detect_source
from fan_curve import FanCurve, default_stages, compact_stages, normalize_stages
from display import Display
from cpu_power import CpuPower
from power_ownership import PowerOwnership
from factory_defaults import ObservedDefaults
from mode_policies import fan_policy,power_policy,policies
from hotkeys import Hotkeys,next_mode
from lighting_animation import LightingAnimation
from lighting_effects import SOFTWARE_EFFECTS
from lighting_settings import startup_lighting


class Worker(QObject):
    snapshot = Signal(dict)
    lighting_frame = Signal(list)
    done = Signal(str, str)
    calibration_progress=Signal(str)
    calibration_finished=Signal(str)
    def __init__(self):
        super().__init__()
        self.hardware = Hardware()
        self.gpu_mode = GpuMode()
        self.system_power=SystemPower(parent=self)
        self.source_profiles=SourceProfiles()
        self.config_store=ConfigStore()
        self.calibrator=Calibrator(root=self.hardware.root,config_store=self.config_store)
        self.calibration_enabled=not self.calibrator.needs_calibration()
        self.calibration_cycle=None
        self.shutting_down=False
        self.animator=LightingAnimation(self)

        self.curve = None
        self.display = Display()
        self.cpu_power = CpuPower()
        self.power_ownership=PowerOwnership(self.cpu_power)
        try:
            self.observed_defaults=ObservedDefaults()
            self._capture_startup_defaults()
        except (OSError,ValueError):self.observed_defaults=None
        self.display_data = None
        self.last_display_poll = 0
        self.auto_refresh = False
        self.last_ac = None
        self.fan_policies = {}
        self.power_policies = {}
        self.last_sensor_poll = float('-inf')
        self.cached_data=None
        self.state_dirty=True
        self.source_dirty=True
        self.cpu_dirty=True
        self.last_policy_mode = None
        self.overlay_demand = {"cpu": set(), "gpu": set(), "visible": False}
    def _capture_startup_defaults(self):
        if not self.observed_defaults:return
        profiles=self.calibrator.cache
        # Also capture current active mode from live hardware if available
        current_profile=self.hardware.bridge_read('profile')
        live_domains=self.cpu_power.capture()
        boost=self.cpu_power.boost()
        for mode_name,mode_val in MODES.items():
            path=self.observed_defaults._path(mode_val)
            if not path.exists():
                if current_profile and str(mode_val)==str(current_profile) and live_domains:
                    try:self.observed_defaults.capture_snapshot(mode_val,live_domains,boost if boost is not None else True)
                    except Exception:pass
                elif mode_name in profiles:
                    prof=profiles[mode_name]
                    domains={'intel-rapl-mmio:0':{'pl1':prof['pl1'],'pl2':prof['pl2'],'tau':prof['tau']}}
                    try:self.observed_defaults.capture_snapshot(mode_val,domains,True)
                    except Exception:pass
    @Slot()
    def start(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.fan_timer=QTimer(self)
        self.fan_timer.setTimerType(Qt.PreciseTimer)
        self.fan_timer.timeout.connect(self.poll)
        self.poll()
    @Slot()
    def poll(self):
        if getattr(getattr(self,'calibration_cycle',None),'active',False) is True:return
        now=time.monotonic()
        sensor_due=now-self.last_sensor_poll>=1.0
        if not sensor_due and not self.state_dirty:return
        try:
            from telemetry_demand import demand
            initial=self.cached_data is None
            mode=self.hardware.control_read('profile')
            custom=bool(self.curve or self.fan_policies.get(mode,{}).get('kind')=='Custom')
            cpu_req,gpu_req=demand(self.overlay_demand,custom)
            if not sensor_due:cpu_req,gpu_req=set(),set()
            if initial:
                data=self.hardware.snapshot(requested=cpu_req)
            else:
                data=dict(self.cached_data)
                data.update(getattr(self.hardware,'_control_cache',{}))
                if cpu_req:data.update(self.hardware.sensor_snapshot(cpu_req))
            data['telemetry_sample']=sensor_due and bool(cpu_req or gpu_req)
            if sensor_due:self.last_sensor_poll=now
            calibration_profile=data.get("profile")

            if self.animator.active:data['led_timeout']=str(self.animator.timeout)
            if gpu_req:data['gpu'] = self.hardware.gpu_snapshot(requested=gpu_req)
            elif initial:data['gpu']={}
            if custom:data['gpu_temp']=(data['gpu'] or {}).get('temperature')
            if not hasattr(self,'gpu_mode_data'):self.gpu_mode_data=self.gpu_mode.snapshot()
            data['gpu_mode'] = self.gpu_mode_data
            if self.last_display_poll==0:
                try: self.display_data = self.display.snapshot()
                except Exception: self.display_data = None
                self.last_display_poll = time.monotonic()
            data['display'] = self.display_data
            if self.cpu_dirty or initial:
                data['cpu_power']=self.cpu_power.snapshot()
                data['observed_defaults']=self.observed_defaults.status() if self.observed_defaults else {}
                self.cpu_dirty=False
            if self.source_dirty or initial:
                self.source_data=detect_source(self.hardware.root)
                self.ac_data=any(self.hardware.read(p/'online')=='1' for p in (self.hardware.root/'class/power_supply').glob('*'))
                self.source_dirty=False
            ac=self.ac_data
            data['ac'] = ac
            data['auto_refresh'] = self.auto_refresh
            if self.auto_refresh and ac != self.last_ac and self.display_data:
                modes = sorted(self.display_data['modes'],key=lambda m:m['refreshRate'])
                self.display.apply(modes[-1 if ac else 0]['id'])
                self.last_display_poll = 0
            self.last_ac = ac
            source=self.source_data
            current_name=next((n for n,v in MODES.items() if str(v)==str(data.get('profile'))),None)
            decision=self.source_profiles.poll(source,current_name)
            if decision is not None:
                self.power_ownership.release()
                if self.curve:self.curve=None;self.hardware.write('fan_mode',0)
                self.hardware.write('profile',MODES[decision]);data['profile']=str(MODES[decision])
                self.last_policy_mode=None
            data['power_source']=source
            if initial or str(self.last_policy_mode)!=str(data.get('profile')):
                data['system_power']=self.system_power.sync(data.get('profile'))
            current=data.get('profile')
            if current is not None and current != self.last_policy_mode:
                previous_mode=self.last_policy_mode
                self.last_policy_mode=current
                if previous_mode is not None and previous_mode!=current:self.power_ownership.release()
                if previous_mode is not None and self.curve:
                    self.curve=None
                    self.hardware.write('fan_mode',0)
                policy=self.fan_policies.get(current)
                if policy:
                    self.curve=None
                    if policy['kind']=='Custom':
                        self.curve=FanCurve(stages=policy.get('stages'), delay=policy.get('delay', 2))
                    else: self.hardware.write('fan_mode',1 if policy['kind']=='Max' else 0)
                power=self.power_policies.get(current)
                if power:
                    limits = {k: v for k, v in power.items() if k != 'boost'}
                    self.power_ownership.apply(**limits)
                    if 'boost' in power:self.cpu_power.set_boost(power['boost'])
                data['cpu_power']=self.cpu_power.snapshot()
                self.cpu_dirty=False
            if self.curve and sensor_due and 'cpu_temp' in cpu_req:
                try:
                    cpu = float(data.get('cpu_temp') or 0)
                    gpu = float(data.get('gpu_temp') or 0)
                    if not 0 < cpu <= 125: raise RuntimeError('CPU temperature unavailable; custom fans stopped')
                    duty = self.curve.target(cpu_temp=cpu, gpu_temp=(gpu if 0 < gpu <= 125 else 0))
                    self.hardware.fan_duty(*duty)
                    data['custom_fans'] = list(duty)
                except Exception as exc:
                    self.curve = None
                    self.hardware.write('fan_mode',0)
                    self.done.emit('Custom fans',str(exc))
            if (self.calibration_enabled and self.state_dirty and data.get('profile')==calibration_profile and
                    self.hardware.control_read('profile')==calibration_profile):
                data['cpu_policy_active']=bool(self.power_ownership.expected)
                data['calibration']=self.calibrator.update(data)
            self.cached_data=data
            self.state_dirty=False
            self.snapshot.emit(data)
            self.update_sampling_timers()
        except Exception as exc:
            self.done.emit('Telemetry', str(exc))
    def update_sampling_timers(self):
        overlay=bool(self.overlay_demand.get('visible') and any(m!='None' for m in self.overlay_demand.get('cpu',set())|self.overlay_demand.get('gpu',set())))
        for timer,needed in ((self.timer,overlay),(self.fan_timer,bool(self.curve))):
            if needed:
                if not timer.isActive():timer.start(1000)
            else:timer.stop()

    @Slot(str, object)
    def command(self, name, args):
        if getattr(getattr(self,'calibration_cycle',None),'active',False) is True:
            if name in ('profile','cycle_mode','cpu_boost','cpu_power','power_policy','reset_power_policy','mode_policies','fan_policy','fan_mode','curve','calibrate'):
                self.done.emit(name,'Wait for calibration to finish.');return
        self.state_dirty=True
        if name in ('profile','cycle_mode','power_policy','reset_power_policy','cpu_power','cpu_boost','mode_policies'):self.cpu_dirty=True
        try:
            if name == 'refresh_ui':
                pass
            elif name=='power_source_event':
                self.source_dirty=True
            elif name == 'overlay_metrics':
                self.overlay_demand = {
                    'cpu': set(args.get('cpu', [])),
                    'gpu': set(args.get('gpu', [])),
                    'visible': bool(args.get('visible', False))
                }
                if not self.overlay_demand['visible']:self.timer.stop()
            elif name=='calibrate':
                if args:
                    self.begin_calibration()
                    return
                self.calibration_enabled=False
            elif name=='source_profiles':
                self.source_profiles.configure(args)
            elif name == 'gpu_mode':
                message = self.gpu_mode.stage(args)
                if hasattr(self,'gpu_mode_data'):del self.gpu_mode_data
                self.done.emit('GPU boot setting: '+message, '')
                self.poll()
                return
            elif name=='cycle_mode':
                current=int(self.hardware.bridge_read('profile') or 1)
                ac=any(self.hardware.read(p/'online')=='1' for p in (self.hardware.root/'class/power_supply').glob('*'))
                self.curve=None
                target=next_mode(current,ac)
                self.source_profiles.manual_override(next(n for n,v in MODES.items() if v==target))
                self.hardware.write('profile',target);self.last_policy_mode=None
            elif name == 'mode_policies':
                self.fan_policies=policies(args.get('fans',{}),fan_policy)
                self.power_policies=policies(args.get('power',{}),power_policy)
                self.last_policy_mode=None
            elif name in ('fan_policy','power_policy'):
                mode=str(args['mode'])
                if mode not in {str(v) for v in MODES.values()}:raise ValueError('Unknown performance mode')
                if name=='fan_policy': self.fan_policies[mode]=fan_policy(args['policy'])
                else: self.power_policies[mode]=power_policy(args['policy'])
                if self.hardware.bridge_read('profile')==mode:self.last_policy_mode=None
            elif name == 'gpu_offsets':
                from gpu_offsets import GpuOffsets
                GpuOffsets().apply(args['mode'], args['ct'], args['db'], args.get('cp'))
            elif name == 'cpu_prochot':
                from cpu_prochot import CpuProchot
                snap = CpuProchot().apply(int(args))
                self.done.emit(
                    f'PROCHOT offset set to {snap.offset_celsius}°C (activates at {snap.activation_celsius}°C)',
                    '')
                return
            elif name=='cpu_boost':
                self.cpu_power.set_boost(args)
            elif name == 'cpu_power':
                self.power_ownership.apply(**args)
            elif name=='reset_power_policy':
                mode=str(args)
                self.power_policies.pop(mode,None)
                if self.hardware.bridge_read('profile')==mode:
                    self.power_ownership.release()
                    if self.observed_defaults:
                        try:
                            self.observed_defaults.reset(int(mode),self.cpu_power,lambda:int(self.hardware.bridge_read('profile')),controller_active=False)
                        except Exception:pass
            elif name == 'display':
                self.auto_refresh = False
                self.display.apply(args)
                self.last_display_poll = 0
            elif name == 'auto_refresh':
                self.auto_refresh = bool(args)
                self.last_ac = None
            elif name == 'curve':
                self.curve = FanCurve(**args)
            elif name=='keyboard_brightness':
                if self.animator.active:
                    self.animator.args['brightness']=args['brightness'];self.animator.wake_at=time.monotonic();self.animator.tick()
                else:
                    values=dict(args);sync=values.pop('sync_logo',False)
                    self.hardware.lighting(**values)
                    if sync:self.hardware.logo_lighting(average_color(values['colors']),values['brightness'],'Static',values['speed'])
            elif name=='logo_lighting':
                if self.animator.active:self.animator.args['sync_logo']=False
                self.hardware.logo_lighting(**args)
            elif name=='led_timeout' and self.animator.active:
                self.animator.timeout=args;self.animator.restore_timeout=args
            elif name == 'lighting':
                if args['effect'] in SOFTWARE_EFFECTS:self.animator.start(args)
                else:
                    self.animator.stop()
                    values=dict(args);sync=values.pop('sync_logo',False)
                    self.hardware.lighting(**values)
                    if sync:self.hardware.logo_lighting(average_color(values['colors']),values['brightness'],'Static' if values['effect'] not in ('Breathing','Neon') else values['effect'],values['speed'])
            else:
                if name in ('profile','fan_mode'): self.curve = None
                if name == 'profile':
                    self.source_profiles.manual_override(next(n for n,v in MODES.items() if v==args))
                self.hardware.write(name, args)
                if name=='profile':self.last_policy_mode=None
            self.done.emit(name, '')
        except Exception as exc:
            self.done.emit(name, str(exc))
        self.poll()

    def begin_calibration(self):
        from calibration_cycle import CalibrationCycle
        self.timer.stop()
        self.fan_timer.stop()
        try:
            self.power_ownership.release()
            if self.curve:self.hardware.write('fan_mode',0);self.curve=None
            base=dict(self.cached_data or {})
            base.pop('custom_fans',None)
            base.pop('gpu',None)
            cycle=CalibrationCycle(self.hardware,self.cpu_power,self.calibrator,base,parent=self)
            self.calibration_cycle=cycle
            cycle.progress.connect(self.calibration_progress)
            cycle.done.connect(self.finish_calibration)
            cycle.start()
        except Exception as exc:self.finish_calibration(str(exc))

    def finish_calibration(self,error):
        self.calibration_enabled=not self.calibrator.needs_calibration()
        self.last_policy_mode=None;self.cpu_dirty=True;self.state_dirty=True
        if not self.shutting_down:
            self._capture_startup_defaults()
            self.poll()
        self.calibration_finished.emit(error)

    @Slot()
    def shutdown(self):
        self.shutting_down=True
        if self.calibration_cycle is not None:self.calibration_cycle.cancel()
        self.timer.stop()
        self.fan_timer.stop()
        try:self.animator.stop()
        except Exception as exc:self.done.emit('Lighting',str(exc))
        self.hardware.close_lighting()
        self.curve = None
        errors=[]
        try:self.power_ownership.release()
        except Exception as exc:errors.append(str(exc))
        try: self.hardware.write('fan_mode',0)
        except Exception as exc: errors.append(str(exc))
        power_state=self.system_power.shutdown()
        if power_state.get('error'):errors.append(power_state['error'])
        if errors: self.done.emit('Shutdown','; '.join(errors))

class Window(QMainWindow):
    command = Signal(str, object)
    feedback = Signal(str,bool)
    def __init__(self):
        super().__init__()
        from tooltip_policy import install_no_tooltips
        install_no_tooltips(QApplication.instance())
        self.quitting = False
        self._helpers_started=False
        self.auto_hidden_windows=[]
        for effect in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip, Qt.UI_AnimateToolBox):
            QApplication.setEffectEnabled(effect, False)
        legacy = QSettings('PreySense', 'Linux')
        self.config_store = getattr(self.worker, 'config_store', None) or ConfigStore()
        self.settings = JsonSettings(self.config_store)
        self.settings.ensure_migrated(legacy)
        self.setWindowTitle('PreySense · Linux')
        self.resize(840, 650)
        icon = Path(__file__).resolve().parent / 'assets/appicon.svg'
        self.setWindowIcon(QIcon(str(icon)))
        self.colors = [QColor(c) for c in self.settings.value('colors', ['#28d8ca']*4)]
        self.thread = QThread(self)
        self.worker = Worker()
        self._calibration_needed=not self.worker.calibration_enabled
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.command.connect(self.worker.command)
        self.worker.snapshot.connect(self.update_data)
        self.worker.done.connect(self.finished)
        self.thread.finished.connect(self.worker.deleteLater)
        self.build()
        from mode_toast import ModeToast
        self.mode_toast=ModeToast(self)
        self._confirmed_profile=None
        self._profile_preview=None
        self._last_ac=False
        from mode_switch import ModeSwitch
        self.mode_switch=ModeSwitch(lambda mode:self.apply('profile',mode,immediate=True),parent=self)
        from power_events import PowerEvents
        self.power_events=PowerEvents(self)
        self.power_events.changed.connect(lambda:self.command.emit('power_source_event',None))
        self.setup_tray()
        from appearance import Appearance
        self.appearance=Appearance(self)
        self.hotkeys=Hotkeys(self)
        self.hotkeys.predator.connect(self.toggle_window)
        self.hotkeys.mode.connect(self.request_profile)
        self.hotkeys.overlay.connect(lambda:self.overlay_toggle.setChecked(not self.overlay_toggle.isChecked()))
        self.hotkeys.turbo.connect(self.request_next_profile)
        self.thread.start()
        try:
            source_policies=json.loads(self.settings.value('source_profiles','{}'))
            source_policies.setdefault('Battery','Eco')
            source_policies.setdefault('AC','Balanced')
            self.settings.setValue('source_profiles',json.dumps(source_policies))
            self.command.emit('source_profiles',source_policies)
        except (ValueError,TypeError) as exc:self.report_error(str(exc))
        try:
            for name,args in startup_lighting(self.settings):QTimer.singleShot(1000,lambda name=name,args=args:self.command.emit(name,args))
        except (TypeError,ValueError) as exc:self.report_error(str(exc))
        if self.settings.value('auto_refresh',False,type=bool):QTimer.singleShot(100,lambda:self.command.emit('auto_refresh',True))
        self.overlay_toggle.setChecked(self.settings.value('overlay_visible',False,type=bool))
        self.overlay_toggle.toggled.connect(lambda enabled:self.settings.setValue('overlay_visible',enabled))
        QTimer.singleShot(150, lambda: self.command.emit('overlay_metrics', self.overlay.requested_metrics()))
        self.saved_gpu_policies={}
        try:
            self.saved_fan_policies=policies(json.loads(self.settings.value('fan_policies','{}')),fan_policy)
            self.saved_power_policies=policies(json.loads(self.settings.value('power_policies','{}')),power_policy)
            loaded_gpu=json.loads(self.settings.value('gpu_policies','{}') or '{}')
            if isinstance(loaded_gpu, dict):
                self.saved_gpu_policies=loaded_gpu
            values=dict(fans=self.saved_fan_policies,power=self.saved_power_policies)
            if values['fans'] or values['power']:QTimer.singleShot(100,lambda:self.command.emit('mode_policies',values))
        except (KeyError,TypeError,ValueError):
            self.saved_fan_policies={};self.saved_power_policies={};self.saved_gpu_policies={}

    def build(self):
        root = QWidget(); layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 20); layout.setSpacing(18)
        heading = QLabel('PREYSENSE'); heading.setObjectName('heading'); layout.addWidget(heading)
        self.subtitle = QLabel('Linux control center'); self.subtitle.setObjectName('muted'); layout.addWidget(self.subtitle)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        dashboard = QWidget(); d = QVBoxLayout(dashboard); d.setSpacing(18)
        grid = QGridLayout(); self.metrics = {}
        for i, (key, text) in enumerate([('cpu_temp','CPU temperature'),('gpu_temp','GPU temperature'),
                         ('cpu_fan','CPU fan'),('gpu_fan','GPU fan'),('cpu_usage','CPU load'),('memory','Memory')]):
            box = QGroupBox(text); inner = QVBoxLayout(box)
            label = QLabel('—'); label.setObjectName('metric'); inner.addWidget(label)
            self.metrics[key] = label; grid.addWidget(box, i//3, i%3)
        d.addLayout(grid)
        modebox = QGroupBox('Performance'); row = QHBoxLayout(modebox)
        self.mode = QComboBox(); self.mode.addItems(MODES)
        self.mode.setCurrentText('Balanced'); row.addWidget(self.mode)
        self.mode_apply = QPushButton('Apply mode'); self.mode_apply.clicked.connect(lambda: self.apply('profile', MODES[self.mode.currentText()])); row.addWidget(self.mode_apply)
        self.mode_current = QLabel('Current: —'); row.addWidget(self.mode_current); d.addWidget(modebox)
        fanbox = QGroupBox('Cooling'); row = QHBoxLayout(fanbox)
        self.fan_auto = QPushButton('Automatic'); self.fan_auto.clicked.connect(lambda: self.apply('fan_mode', 0)); row.addWidget(self.fan_auto)
        self.fan_max = QPushButton('Maximum'); self.fan_max.clicked.connect(lambda: self.apply('fan_mode', 1)); row.addWidget(self.fan_max)
        self.fan_current = QLabel('Firmware controlled'); row.addWidget(self.fan_current); d.addWidget(fanbox)
        displaybox = QGroupBox('Display'); displayrow = QHBoxLayout(displaybox)
        from ui_controls import CenteredComboBox
        self.refresh = CenteredComboBox(); displayrow.addWidget(self.refresh)
        self.refresh_apply = QPushButton('Apply refresh rate'); self.refresh_apply.clicked.connect(lambda: self.apply('display',self.refresh.currentData())); displayrow.addWidget(self.refresh_apply)
        self.refresh_auto = QCheckBox('Auto on AC / battery'); self.refresh_auto.toggled.connect(lambda checked: self.apply('auto_refresh',checked)); displayrow.addWidget(self.refresh_auto)
        d.addWidget(displaybox)
        self.battery = QLabel('Battery: —'); d.addWidget(self.battery)
        charge = QHBoxLayout(); charge.addWidget(QLabel('Charge limit'))
        self.charge = QComboBox(); self.charge.addItems(['80%', '100%']); charge.addWidget(self.charge)
        self.charge_apply = QPushButton('Apply limit'); self.charge_apply.clicked.connect(lambda: self.apply('battery_limit', int(self.charge.currentText()[:-1]))); charge.addWidget(self.charge_apply); charge.addStretch(); d.addLayout(charge)
        d.addStretch(); self.tabs.addTab(dashboard, 'Dashboard')
        curvepage = QWidget(); c = QVBoxLayout(curvepage)
        self.fan_stages = default_stages(1)
        self.fan_channel_gpu = False
        delayrow = QHBoxLayout(); delayrow.addWidget(QLabel('Fan control delay (seconds)')); self.curve_delay = QDoubleSpinBox(); self.curve_delay.setRange(0,5); self.curve_delay.setSingleStep(1); self.curve_delay.setValue(2); delayrow.addWidget(self.curve_delay); c.addLayout(delayrow)
        try:
            saved_curve=json.loads(self.settings.value('fan_curve','null'))
            if saved_curve and saved_curve.get('stages'):
                FanCurve(stages=saved_curve['stages'], delay=saved_curve.get('delay', 2))
                self.fan_stages = normalize_stages(saved_curve['stages'])
                self.curve_delay.setValue(saved_curve['delay'])
        except (ValueError,TypeError,KeyError): pass
        self.curve_apply = QPushButton('Start custom fan curves'); self.curve_apply.clicked.connect(self.apply_curve); c.addWidget(self.curve_apply)
        stop = QPushButton('Stop curves · return to automatic'); stop.clicked.connect(lambda: self.apply('fan_mode',0)); c.addWidget(stop)
        self.tabs.addTab(curvepage,'Fans')
        lighting = QWidget(); l = QVBoxLayout(lighting); l.setSpacing(20)
        l.addWidget(QLabel('Four-zone keyboard lighting'))
        row = QHBoxLayout(); self.color_buttons = []
        for i in range(4):
            button = QPushButton(f'Zone {i+1}'); button.clicked.connect(lambda checked=False, i=i: self.choose_color(i)); row.addWidget(button); self.color_buttons.append(button)
        l.addLayout(row); self.paint_colors()
        self.effect = QComboBox(); self.effect.addItems([*EFFECTS,*SOFTWARE_EFFECTS]); self.effect.setCurrentText(self.settings.value('effect', 'Static')); l.addWidget(self.effect)
        l.addWidget(QLabel('Brightness')); self.brightness = QSlider(Qt.Horizontal); self.brightness.setRange(0,100); self.brightness.setValue(int(self.settings.value('brightness',100))); l.addWidget(self.brightness)
        l.addWidget(QLabel('Animation speed')); self.speed = QSlider(Qt.Horizontal); self.speed.setRange(0,10); self.speed.setValue(max(0,min(10,int(self.settings.value('speed',5))))); l.addWidget(self.speed)
        self.rgb_apply = QPushButton('Apply keyboard lighting'); self.rgb_apply.clicked.connect(self.apply_lighting); l.addWidget(self.rgb_apply)
        self.rgb_status = QLabel('Detecting keyboard…'); self.rgb_status.setWordWrap(True); l.addWidget(self.rgb_status); l.addStretch(); self.tabs.addTab(lighting,'Lighting')
        tuningpage = QWidget(); t = QVBoxLayout(tuningpage)
        description = QLabel('CPU limits use the Linux Intel RAPL interface. Both MSR and MMIO domains are updated when available, with readback and rollback on error. Values are limited to those captured at app startup. Firmware may override these limits later.'); description.setWordWrap(True); t.addWidget(description)
        self.power_pl1 = QSpinBox(); self.power_pl1.setRange(5,999); self.power_pl1.setSuffix(' W')
        self.power_pl2 = QSpinBox(); self.power_pl2.setRange(5,999); self.power_pl2.setSuffix(' W')
        for title,spin in [('CPU PL1 (sustained)',self.power_pl1),('CPU PL2 (burst)',self.power_pl2)]:
            row=QHBoxLayout(); row.addWidget(QLabel(title)); row.addWidget(spin); t.addLayout(row)
        self.power_apply=QPushButton('Apply CPU limits'); self.power_apply.clicked.connect(lambda:self.apply('cpu_power',dict(pl1=self.power_pl1.value(),pl2=self.power_pl2.value()))); t.addWidget(self.power_apply)
        self.power_state=QLabel('Intel RAPL unavailable'); self.power_state.setWordWrap(True); t.addWidget(self.power_state); t.addStretch(); self.tabs.addTab(tuningpage,'Tuning')
        self.power_initialized = False
        from metrics_overlay import HardwareOverlay as MetricsOverlay
        self.overlay=MetricsOverlay(self.settings)
        self.overlay.metrics_changed.connect(lambda req: self.command.emit('overlay_metrics', req))
        platform = QWidget(); p = QVBoxLayout(platform)
        self.gpu = QLabel(); self.gpu.setWordWrap(True); p.addWidget(self.gpu)
        note = QLabel('Linux support\n\nPerformance modes, automatic/maximum fans, temperatures, fan RPM, battery limit and ENEK5130 keyboard effects use native Linux interfaces.\n\nSee Linux Documentation for feature status and Intel RAPL controls. No OpenCore or Windows driver is installed by this app.\n\nThe hardware bridge currently supports the Predator PHN16S-71 only.'); note.setWordWrap(True); p.addWidget(note)
        self.platform_controls = {}
        for name,title,choices in [
            ('boot_sound','Boot sound',[('Off',0),('On',1)]),
            ('led_timeout','Keyboard lighting timeout',[('Never',0),('30 seconds',30)]),
            ('usb_charging','USB charging when powered off',[('Off',0),('Until battery 10%',10),('Until battery 20%',20),('Until battery 30%',30)]),
            ('lcd_overdrive','LCD overdrive',[('Off',0),('On',1)])]:
            row = QHBoxLayout(); row.addWidget(QLabel(title)); combo = QComboBox()
            for text,value in choices: combo.addItem(text,value)
            row.addWidget(combo); button = QPushButton('Apply'); button.clicked.connect(lambda checked=False,name=name,combo=combo: self.apply(name,combo.currentData())); row.addWidget(button)
            state = QLabel('—'); row.addWidget(state); p.addLayout(row); self.platform_controls[name] = (combo,button,state)
        self.overlay_toggle = QCheckBox('Show desktop metrics overlay'); self.overlay_toggle.toggled.connect(self.overlay.setVisible); p.addWidget(self.overlay_toggle)
        self.autostart = QCheckBox('Start PreySense when I log in'); self.autostart.setChecked((Path.home()/'.config/autostart/preysense.desktop').exists()); self.autostart.toggled.connect(self.set_autostart); p.addWidget(self.autostart)
        self.diagnostics = QPlainTextEdit(); self.diagnostics.setReadOnly(True); self.diagnostics.setMaximumHeight(180); p.addWidget(self.diagnostics); p.addStretch(); self.tabs.addTab(platform,'System')
        self.status = QLabel('Connecting to hardware…'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.setCentralWidget(root)
        import design
        design.build(self)

    def prompt_startup_calibration(self):
        if not self._calibration_needed or self.quitting:return
        from calibration_ui import confirm_calibration,run_calibration
        if confirm_calibration(self):
            self._calibration_needed=not run_calibration(self)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu(); show = menu.addAction('PreySense'); show.triggered.connect(self.show_window)
        menu.addAction('Quit').triggered.connect(self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()

    def toggle_window(self):
        if self.isVisible():
            owned=set(self.findChildren(QWidget))
            self.auto_hidden_windows=[w for w in QApplication.topLevelWidgets() if w in owned and w is not self.overlay and w.isVisible()]
            for window in self.auto_hidden_windows:window.hide()
            self.hide()
        else:self.show_window()
    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,'command'):self.command.emit('refresh_ui',None)

    def show_window(self):
        self.showNormal();self.raise_();self.activateWindow()
        for window in self.auto_hidden_windows:
            window.show();window.raise_()
        self.auto_hidden_windows=[]
    def stage_gpu_mode(self, mode):
        from ui_controls import confirm_gpu_mode
        current = getattr(self, '_gpu_firmware_mode', None)
        for name, tile in getattr(self, 'gpu_tiles', {}).items():
            tile.setChecked(name == current)
        if current == mode:
            return
        restart = requires_confirmation(current, mode)
        if restart and not confirm_gpu_mode(self, mode):
            return
        self._gpu_restart_pending = restart
        self.apply('gpu_mode', mode)
    def request_profile(self,mode):
        if type(mode) is not int or mode not in MODES.values():return
        self._profile_preview=mode
        if mode==self._confirmed_profile:self.mode_switch.cancel();self._profile_preview=None
        else:self.mode_switch.request(mode)
        for value,tile in self.mode_tiles.items():tile.setChecked(value==mode)

    def request_next_profile(self):
        current=self._profile_preview if self._profile_preview is not None else self._confirmed_profile
        self.request_profile(next_mode(current if current is not None else 1,self._last_ac))

    def apply(self, name, value, immediate=False):
        if name=='profile':
            if not immediate:self.request_profile(value);return
            self.mode_switch.cancel();self._profile_preview=value
        if name=='auto_refresh':self.settings.setValue('auto_refresh',bool(value))
        elif name=='display':self.settings.setValue('auto_refresh',False)
        elif name=='led_timeout':
            if type(value) is not int or not 0<=value<=120:raise ValueError('Timeout must be 0–120 seconds')
            self.settings.setValue('led_timeout',value)
        self.status.setText('Applying setting…');self.feedback.emit('Applying setting…',False); self.command.emit(name, value)
    def report_error(self,message):
        self.status.setText(message);self.feedback.emit(message,True)
    def finished(self, name, error):
        labels={'cpu_power':'CPU limits','power_policy':'CPU profile','gpu_offsets':'GPU offsets','cpu_prochot':'PROCHOT','fan_policy':'Fan profile','fan_mode':'Fan mode','profile':'Performance mode','lighting':'Keyboard lighting','led_timeout':'Backlight timeout','usb_charging':'USB charging','battery_limit':'Battery limit','boot_sound':'Boot sound','display':'Refresh rate','auto_refresh':'Automatic refresh','mode_policies':'Saved mode policies'}
        if name=='profile' and error:self.mode_switch.cancel();self._profile_preview=None
        label=labels.get(name,name.replace('_',' ').capitalize())
        text=(f'{label}: {error}' if error else name if name.startswith('GPU boot setting: ') else f'{label} applied successfully')
        self.status.setText(text);self.feedback.emit(text,bool(error))
        if name=='gpu_mode' or name.startswith('GPU boot setting: '):
            restart = getattr(self,'_gpu_restart_pending',False)
            self._gpu_restart_pending = False
            if restart and not error:
                import subprocess
                result = subprocess.run(['systemctl','reboot'],capture_output=True,text=True)
                if result.returncode:self.report_error('GPU mode saved, but restart failed: '+result.stderr.strip())
    def set_fan_editor_kind(self,kind):
        self.fan_editor_kind=kind
        for name,button in self.fan_kind_buttons.items():button.setChecked(name==kind)
        if hasattr(self,'fan_editor_state'):self.fan_editor_state(kind)
    def fan_editor_policy(self):
        policy=dict(kind=self.fan_editor_kind)
        if self.fan_editor_kind=='Custom':
            policy.update(stages=compact_stages(self.fan_stages), delay=self.curve_delay.value())
        return fan_policy(policy)
    def apply_fan_policy(self,save=False,activate=None):
        try:policy=self.fan_editor_policy()
        except (ValueError,KeyError) as exc:self.report_error(str(exc));return
        mode=str(self.fan_profile.currentData())
        if save:
            self.saved_fan_policies[mode]=policy
            self.settings.setValue('fan_policies',json.dumps(self.saved_fan_policies))
        self.apply('fan_policy',dict(mode=mode,policy=policy))
    def load_fan_policy(self):
        policy=getattr(self,'saved_fan_policies',{}).get(str(self.fan_profile.currentData()),dict(kind='Auto'))
        self.set_fan_editor_kind(policy['kind'])
        try:mode=int(self.fan_profile.currentData())
        except (ValueError,TypeError):mode=1
        if policy['kind']=='Custom' and policy.get('stages'):
            self.fan_stages=normalize_stages(policy['stages'],mode)
            self.curve_delay.setValue(int(policy.get('delay',2)))
        else:
            self.fan_stages=default_stages(mode)
            self.curve_delay.setValue(2)
        if hasattr(self,'refresh_fan_graph'):
            self.refresh_fan_graph()

    def apply_boost_setting(self, enabled):
        mode = str(self.power_profile.currentData())
        if str(self.power_profile.currentData()) == str(self._confirmed_profile):
            self.apply('cpu_boost', enabled)
        if mode in getattr(self, 'saved_power_policies', {}):
            self.saved_power_policies[mode]['boost'] = enabled
            self.settings.setValue('power_policies', json.dumps(self.saved_power_policies))
            self.apply('power_policy', dict(mode=mode, policy=self.saved_power_policies[mode]))

    def refresh_prochot_ui(self):
        from cpu_prochot import CpuProchot
        snap = CpuProchot().read()
        locked = bool(self.settings.value('factory_prochot_locked', False, type=bool)) if snap is None else snap.locked
        if snap is None:
            self.prochot_activation.setText('PROCHOT N/A')
            self.tjmax_label.setText('Tj-Max —')
            self.prochot_offset.setEnabled(False)
            self.prochot_switch.setEnabled(False)
            self.prochot_switch.blockSignals(True); self.prochot_switch.setChecked(False); self.prochot_switch.blockSignals(False)
            return
        if self.settings.value('factory_prochot_offset', None) is None:
            self.settings.setValue('factory_prochot_offset', snap.offset_celsius)
            self.settings.setValue('factory_prochot_locked', snap.locked)
            self.settings.setValue('factory_tjmax', snap.tjmax_celsius)
        offset = self.settings.value('prochot_offset', None)
        try:
            offset = int(offset) if offset is not None else snap.offset_celsius
        except (TypeError, ValueError):
            offset = snap.offset_celsius
        self.prochot_offset.spin.blockSignals(True)
        self.prochot_offset.setValue(offset)
        self.prochot_offset.spin.blockSignals(False)
        label = f'PROCHOT {snap.tjmax_celsius - offset}°C'
        if locked:
            label += ' - Locked'
        self.prochot_activation.setText(label)
        self.tjmax_label.setText(f'Tj-Max {snap.tjmax_celsius}°C')
        tuning_on = bool(getattr(self, 'tuning_enabled_row', None) and self.tuning_enabled_row.isChecked())
        can_toggle = (not locked) and tuning_on
        self.prochot_switch.setEnabled(can_toggle)
        want = False if locked else bool(self.settings.value('apply_prochot', False, type=bool))
        self.prochot_switch.blockSignals(True); self.prochot_switch.setChecked(want); self.prochot_switch.blockSignals(False)
        def on_prochot_toggle(on):
            self.prochot_offset.setEnabled(bool(on) and can_toggle)
            if on and self.settings.value('prochot_offset', None) is None:
                self.settings.setValue('prochot_offset', self.prochot_offset.value())
        try: self.prochot_switch.toggled.disconnect()
        except TypeError: pass
        self.prochot_switch.toggled.connect(on_prochot_toggle)
        on_prochot_toggle(self.prochot_switch.isChecked())

    def apply_power_policy(self,save=False):
        if hasattr(self,'tuning_enabled_row') and not self.tuning_enabled_row.isChecked():
            self.report_error('Enable Tuning first'); return
        apply_cpu=getattr(self,'apply_cpu_switch',None) is None or self.apply_cpu_switch.isChecked()
        apply_gpu=getattr(self,'apply_gpu_switch',None) is not None and self.apply_gpu_switch.isChecked()
        apply_prochot=getattr(self,'prochot_switch',None) is not None and self.prochot_switch.isChecked()
        mode=str(self.power_profile.currentData())
        if apply_prochot:
            try:
                offset=int(self.prochot_offset.value())
            except (TypeError, ValueError):
                self.report_error('Enter a PROCHOT offset, or turn its switch off.'); return
            if save:
                self.settings.setValue('prochot_offset', offset)
                self.settings.setValue('apply_prochot', True)
            self.apply('cpu_prochot', offset)
        elif save:
            self.settings.setValue('apply_prochot', False)
        if apply_cpu:
            boost_attr = getattr(self, 'cpu_boost', None)
            try:
                fields = dict(pl1=self.power_pl1.value(),pl2=self.power_pl2.value(),tau=self.power_tau.currentData())
                if boost_attr is not None and hasattr(boost_attr, 'isChecked') and type(boost_attr.isChecked()) is bool:
                    fields['boost'] = boost_attr.isChecked()
                policy=power_policy(fields)
            except ValueError as exc:self.report_error(str(exc));return
            if save:
                self.saved_power_policies[mode]=policy
                self.settings.setValue('power_policies',json.dumps(self.saved_power_policies))
            self.apply('power_policy',dict(mode=mode,policy=policy))
        elif save:
            self.saved_power_policies.pop(mode, None)
            self.settings.setValue('power_policies', json.dumps(self.saved_power_policies))
        if apply_gpu and getattr(self, 'gpu_offsets_available', False) and hasattr(self, 'gpu_ct'):
            gpu = dict(mode=int(mode), ct=self.gpu_ct.value(), db=self.gpu_db.value(), cp=self.gpu_cp.value())
            if save:
                self.saved_gpu_policies[mode]=dict(ct=gpu['ct'], db=gpu['db'], cp=gpu['cp'])
                self.settings.setValue('gpu_policies', json.dumps(self.saved_gpu_policies))
            self.apply('gpu_offsets', gpu)
        elif save:
            self.saved_gpu_policies.pop(mode, None)
            self.settings.setValue('gpu_policies', json.dumps(self.saved_gpu_policies))
        if not apply_cpu and not apply_gpu and not apply_prochot:
            self.report_error('Turn on CPU limits, GPU limits, or PROCHOT first.')
    def reset_power_policy(self):
        mode=str(self.power_profile.currentData())
        self.saved_power_policies.pop(mode,None);self.settings.setValue('power_policies',json.dumps(self.saved_power_policies))
        self.saved_gpu_policies.pop(mode, None)
        self.settings.setValue('gpu_policies', json.dumps(self.saved_gpu_policies))
        factory=self.settings.value('factory_prochot_offset', None)
        if factory is not None:
            try:
                self.prochot_offset.setValue(int(factory))
                self.settings.setValue('prochot_offset', int(factory))
            except (TypeError, ValueError):
                pass
        self.settings.setValue('apply_prochot', False)
        if hasattr(self, 'prochot_switch'):
            self.prochot_switch.blockSignals(True); self.prochot_switch.setChecked(False); self.prochot_switch.blockSignals(False)
        if hasattr(self, 'apply_cpu_switch'):
            self.apply_cpu_switch.blockSignals(True); self.apply_cpu_switch.setChecked(False); self.apply_cpu_switch.blockSignals(False)
        if hasattr(self, 'apply_gpu_switch'):
            self.apply_gpu_switch.blockSignals(True); self.apply_gpu_switch.setChecked(False); self.apply_gpu_switch.blockSignals(False)
        if factory is not None and not bool(self.settings.value('factory_prochot_locked', False, type=bool)):
            try: self.apply('cpu_prochot', int(factory))
            except (TypeError, ValueError): pass
        self.apply('reset_power_policy',int(mode))
        self.load_power_policy()
        if hasattr(self, 'refresh_prochot_ui'):
            self.refresh_prochot_ui()
    def load_power_policy(self):
        mode=str(self.power_profile.currentData())
        policy=getattr(self,'saved_power_policies',{}).get(mode)
        if hasattr(self, 'apply_cpu_switch'):
            self.apply_cpu_switch.blockSignals(True)
            self.apply_cpu_switch.setChecked(policy is not None)
            self.apply_cpu_switch.blockSignals(False)
        if not policy:
            from cpu_tuning import observed_policy
            calibration=Calibrator()
            name=next((name for name,value in MODES.items() if value==self.power_profile.currentData()),None)
            cached_prof=calibration.cache.get(name)
            if cached_prof:
                policy=observed_policy({'domains':{'intel-rapl-mmio:0':cached_prof}})
            if policy is None and self.power_profile.currentData()==self._confirmed_profile:
                policy=observed_policy(getattr(self,'_latest_cpu_power',{}))
        if policy:
            self.power_pl1.setValue(policy['pl1']);self.power_pl2.setValue(policy['pl2'])
            if 'tau' in policy:self.power_tau.setCurrentIndex(self.power_tau.findData(policy['tau']))
            boost = policy.get('boost', True)
            if hasattr(self, 'cpu_boost'):
                self.cpu_boost.blockSignals(True); self.cpu_boost.setChecked(boost); self.cpu_boost.blockSignals(False)
        else:
            if hasattr(self, 'cpu_boost'):
                self.cpu_boost.blockSignals(True); self.cpu_boost.setChecked(True); self.cpu_boost.blockSignals(False)
        if hasattr(self,'tau_slider'):
            self.tau_slider.slider.blockSignals(True);self.tau_slider.setValue(max(0,self.power_tau.currentIndex()));self.tau_slider.slider.blockSignals(False)
            self.tau_slider.label_value.setText(self.power_tau.currentText())
        self._cpu_editor_initial=(self.power_pl1.value(),self.power_pl2.value(),self.power_tau.currentData())
        if hasattr(self, 'gpu_ct'):
            saved = getattr(self, 'saved_gpu_policies', {}).get(mode)
            if hasattr(self, 'apply_gpu_switch'):
                self.apply_gpu_switch.blockSignals(True)
                self.apply_gpu_switch.setChecked(bool(saved) and getattr(self, 'gpu_offsets_available', False))
                self.apply_gpu_switch.blockSignals(False)
            live = None
            try:
                from gpu_offsets import GpuOffsets
                live = GpuOffsets().read(int(self.power_profile.currentData()))
            except (OSError, TypeError, ValueError):
                live = None
            values = saved or live or dict(ct=0, db=0, cp=0)
            self.gpu_ct.setValue(int(values.get('ct', 0)))
            self.gpu_db.setValue(int(values.get('db', 0)))
            self.gpu_cp.setValue(int(values.get('cp', 0)))
            if hasattr(self, 'refresh_gpu_nominal'):
                self.refresh_gpu_nominal()
        if hasattr(self, 'apply_cpu_switch'):
            self.apply_cpu_switch.toggled.emit(self.apply_cpu_switch.isChecked())
        if hasattr(self, 'apply_gpu_switch'):
            self.apply_gpu_switch.toggled.emit(self.apply_gpu_switch.isChecked())
    def apply_curve(self):
        args = dict(stages=compact_stages(self.fan_stages), delay=self.curve_delay.value())
        try: FanCurve(stages=args['stages'], delay=args['delay'])
        except ValueError as exc:
            self.report_error(str(exc)); return
        self.settings.setValue('fan_curve',json.dumps(args))
        self.apply('curve',args)
    def choose_color(self, i):
        color = QColorDialog.getColor(self.colors[i], self, f'Zone {i+1}')
        if color.isValid(): self.colors[i] = color; self.paint_colors()
    def paint_colors(self):
        for button, color in zip(self.color_buttons,self.colors):
            foreground = '#111111' if color.lightness()>130 else '#ffffff'
            button.setStyleSheet(f'background:{color.name()};color:{foreground};min-height:64px;')
    def apply_lighting(self):
        if getattr(self,'lighting_target','Keyboard')=='Logo':
            if hasattr(self,'sync_logo_checkbox'):self.sync_logo_checkbox.setChecked(False)
            color=self.colors[0]
            self.settings.setValue('logo_color',color.name());self.settings.setValue('logo_brightness',self.brightness.value());self.settings.setValue('logo_effect',self.effect.currentText());self.settings.setValue('logo_speed',self.speed.value())
            self.apply('logo_lighting',dict(color=(color.red(),color.green(),color.blue()),brightness=self.brightness.value(),effect=self.effect.currentText(),speed=self.speed.value()));return
        self.settings.setValue('colors',[c.name() for c in self.colors]); self.settings.setValue('effect',self.effect.currentText()); self.settings.setValue('brightness',self.brightness.value());self.settings.setValue('speed',self.speed.value())
        self.apply('lighting',dict(colors=[(c.red(),c.green(),c.blue()) for c in self.colors],brightness=self.brightness.value(),effect=self.effect.currentText(),speed=self.speed.value(),sync_logo=getattr(self,'sync_logo',False)))
    def update_data(self, data):
        try:confirmed=int(data.get('profile'))
        except (TypeError,ValueError):confirmed=None
        self._last_ac=bool(data.get('ac',False))
        if confirmed in MODES.values():
            previous=getattr(self,'_confirmed_profile',None)
            if previous is not None and previous!=confirmed:
                self.mode_switch.cancel();self._profile_preview=None
            elif confirmed==self._profile_preview:self._profile_preview=None
            if previous is not None and previous!=confirmed and hasattr(self,'mode_toast'):self.mode_toast.show_mode(confirmed)
            self._confirmed_profile=confirmed
        power=data.get('cpu_power',{})
        self._latest_cpu_power=power
        self.power_apply.setEnabled(power.get('writable',False))
        if hasattr(self,'cpu_boost'):
            self.cpu_boost.setEnabled(power.get('boost_writable',False))
            if str(self.power_profile.currentData()) == str(self._confirmed_profile):
                self.cpu_boost.blockSignals(True);self.cpu_boost.setChecked(bool(power.get('boost', True)));self.cpu_boost.blockSignals(False)
        if hasattr(self,'power_save'):self.power_save.setEnabled(power.get('writable',False))
        if power.get('domains') and not self.power_initialized:
            self.power_initialized=True
            self.load_power_policy()
        domains=list(power.get('domains',{}).values())
        self.power_state.setText(f"Current: PL1 {min(v['pl1'] for v in domains):g} W · PL2 {min(v['pl2'] for v in domains):g} W · Tau {min(v['tau'] for v in domains):.0f} s" if domains else 'CPU power limits unavailable')
        display = data.get('display')
        modes = display['modes'] if display else []
        if [self.refresh.itemData(i) for i in range(self.refresh.count())] != [m['id'] for m in modes]:
            self.refresh.clear()
            for mode in modes:
                self.refresh.addItem(f"{mode['refreshRate']:.0f} Hz",mode['id'])
                self.refresh.setItemData(self.refresh.count()-1,Qt.AlignCenter,Qt.TextAlignmentRole)
            if display: self.refresh.setCurrentIndex(self.refresh.findData(display['current']))
        if display and not self.refresh.hasFocus():
            self.refresh.blockSignals(True);self.refresh.setCurrentIndex(self.refresh.findData(display['current']));self.refresh.blockSignals(False)
        self.refresh_auto.blockSignals(True); self.refresh_auto.setChecked(data.get('auto_refresh',False)); self.refresh_auto.blockSignals(False)
        self.refresh_apply.setEnabled(bool(display)); self.refresh_auto.setEnabled(bool(display));self.refresh.setEnabled(bool(display))
        if data.get('telemetry_sample',True):self.overlay.update_data(data)
        self.subtitle.setText(data['model']+'  ·  Native Linux edition')
        for key, label in self.metrics.items():
            val = data.get(key)
            # A sleeping GPU often returns zero degrees; do not present that as a temperature.
            if val is None or (key.endswith('temp') and str(val)=='0'): text = '—'
            elif key.endswith('fan'):text=f'{int(float(val)/100+.5)*100} RPM'
            else: text = str(val)+(' °C' if key.endswith('temp') else '%')
            label.setText(text)
        current = next((name for name, value in MODES.items() if str(value)==data['profile']), 'Unknown ('+str(data['profile'])+')')
        self.mode_current.setText('Current: '+current)
        self.fan_current.setText('Custom '+str(data['custom_fans'])+'%' if data.get('custom_fans') else {'1 1':'Automatic','2 2':'Maximum'}.get(data['fan_mode'],'Mixed / unavailable'))
        self.curve_apply.setEnabled(data['bridge'] and __import__('os').access('/sys/devices/platform/preysense/fan_duty',__import__('os').W_OK))
        self.battery.setText(f'Battery: {data.get("battery","—")}% · {data.get("battery_status","Unknown")} · Charge limit: {data.get("battery_limit","—")}%')
        for button,name in [(self.mode_apply,'profile'),(self.fan_auto,'fan_mode'),(self.fan_max,'fan_mode'),(self.charge_apply,'battery_limit')]:
            import os
            button.setEnabled(data['bridge'] and os.access(Path('/sys/devices/platform/preysense')/name,os.W_OK))
        import os
        can_rgb = bool(data['keyboard']) and os.access(data['keyboard'],os.W_OK)
        self.rgb_apply.setEnabled(can_rgb)
        self.rgb_status.setText('ENEK5130 keyboard connected' if can_rgb else 'Keyboard unavailable or permission missing. Run linux/install.sh to configure access.')
        for name,(combo,button,state) in self.platform_controls.items():
            value = data.get(name)
            button.setEnabled(name != 'lcd_overdrive' and value is not None and os.access(Path('/sys/devices/platform/preysense')/name,os.W_OK))
            index = combo.findData(int(value)) if value is not None else -1
            if index >= 0 and not combo.property('initialized'):
                combo.setCurrentIndex(index);combo.setProperty('initialized',True)
            state.setText(('Current: '+combo.itemText(index) if index >= 0 else 'Unavailable') + (' · read only' if name == 'lcd_overdrive' else ''))
        self.gpu.setText('GPU: '+(data['gpu'].get('name') or data['gpu'].get('status','Unavailable')))
        self.diagnostics.setPlainText(json.dumps(data,indent=2))
        if self.status.text()=='Connecting to hardware…': self.status.setText('Hardware connected' if data['bridge'] else 'Hardware bridge unavailable. Run linux/install.sh; read-only telemetry is active.')
        import design
        design.update(self,data)
        from platform_windows import update_platform_windows
        update_platform_windows(self,data)
        if hasattr(self,'appearance'):self.appearance.refresh()
    def set_autostart(self, enabled):
        target = Path.home()/'.config/autostart/preysense.desktop'
        if enabled:
            target.parent.mkdir(parents=True,exist_ok=True)
            script = Path(__file__).resolve()
            target.write_text(f'[Desktop Entry]\nType=Application\nName=PreySense\nGenericName=Acer Control Center\nComment=Control your Acer laptop\nKeywords=acer;predator;preysense;prey;sense;\nExec=/usr/bin/python3 "{script}" --tray\nIcon={script.parent}/assets/appicon.svg\n')
        else: target.unlink(missing_ok=True)
    def closeEvent(self,event):
        if self.quitting: event.accept(); return
        if self.tray.isVisible(): self.hide(); event.ignore()
        else: self.quit_app(); event.accept()
    def quit_app(self):
        if self.quitting: return
        self.quitting = True
        self.overlay.hide();self.overlay.close()
        self.hotkeys.stop()
        self.power_events.close()
        self.mode_switch.cancel()
        self.mode_toast.close()
        # Release software fan ownership before stopping the worker.
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(self.worker,'shutdown',Qt.BlockingQueuedConnection)
        self.thread.quit(); self.thread.wait(6000); self.tray.hide(); self.overlay.close()
        from service_lifecycle import stop_helpers
        if self._helpers_started:stop_helpers()
        QApplication.quit()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--version',action='version',version=f'PreySense {__version__}'); parser.add_argument('--tray',action='store_true'); parser.add_argument('--smoke-test',action='store_true'); parser.add_argument('--screenshot'); args = parser.parse_args()
    from desktop_session import configure_platform
    configure_platform()
    app = QApplication(sys.argv); app.setApplicationName('PreySense'); app.setApplicationVersion(__version__); app.setDesktopFileName('preysense'); app.setStyle('Fusion'); app.setStyleSheet(__import__('design').STYLE)
    from app_signals import SignalWakeup
    signal_wakeup=SignalWakeup(app)
    app.aboutToQuit.connect(signal_wakeup.close)
    lock = QLockFile(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)+'/preysense-linux.lock')
    if not args.smoke_test and not lock.tryLock(100):
        client=QLocalSocket(); client.connectToServer(QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)+'/preysense-linux.socket')
        if client.waitForConnected(1000): client.disconnectFromServer()
        else: print('PreySense is already running; open it from the system tray.')
        return 0
    server=None
    if not args.smoke_test:
        server=QLocalServer(); server.setSocketOptions(QLocalServer.UserAccessOption)
        socket_path=QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)+'/preysense-linux.socket'
        QLocalServer.removeServer(socket_path)
        if not server.listen(socket_path): raise RuntimeError('Could not create the PreySense activation socket')
    helpers_started=False
    if not args.smoke_test:
        from service_lifecycle import start_helpers
        helpers_started=start_helpers()
    from kwin_integration import install_instant_effect
    install_instant_effect()
    try:
        window = Window()
    except Exception:
        if helpers_started:
            from service_lifecycle import stop_helpers
            stop_helpers()
        raise
    window._helpers_started=helpers_started
    signal.signal(signal.SIGTERM,lambda *_:window.quit_app())
    signal.signal(signal.SIGINT,lambda *_:window.quit_app())
    if server:
        def activate():
            connection=server.nextPendingConnection()
            window.show_window()
            if connection: connection.deleteLater()
        server.newConnection.connect(activate)
    # Hide to tray when focus leaves PreySense (matching Windows App.xaml.cs Deactivated behavior)
    def on_focus_changed(old, now):
        if now is None and window.isVisible():
            # Check if any window belonging to PreySense (excluding the overlay) is active
            active = QApplication.activeWindow()
            if active is None or active is window.overlay:
                QTimer.singleShot(150, lambda: window.toggle_window() if window.isVisible() and QApplication.activeWindow() in (None, window.overlay) else None)
    app.focusChanged.connect(on_focus_changed)
    if not args.tray or not window.tray.isVisible(): window.show()
    if not args.smoke_test:
        QTimer.singleShot(1000,window.prompt_startup_calibration)
    if args.smoke_test:
        def finish():
            if args.screenshot: window.grab().save(args.screenshot)
            window.quit_app()
        QTimer.singleShot(3500,finish)
    return app.exec()

if __name__ == '__main__': sys.exit(main())
