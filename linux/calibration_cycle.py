"""Missing-only per-mode RAPL capture, using Windows' settle/restore flow.

Run on the hardware worker's Qt thread. This cycles OEM modes, waits for their
power registers to settle, and records observed settings; it runs no benchmark.
The caller pauses automatic/saved policies and releases owned RAPL changes first.
"""
import copy
from PySide6.QtCore import QObject,QTimer,Signal

MODE_ORDER=((6,'Eco'),(0,'Quiet'),(1,'Balanced'),(4,'Performance'),(5,'Turbo'))

class CalibrationCycle(QObject):
    progress=Signal(str)
    done=Signal(str)

    def __init__(self,hardware,cpu_power,calibrator,base_data=None,parent=None,*,
                 ac_online=None,settle_ms=2500,check_ms=150):
        super().__init__(parent)
        self.hardware=hardware;self.cpu_power=cpu_power;self.calibrator=calibrator
        self.base_data=copy.deepcopy(base_data or {})
        self.ac_online=ac_online or self._ac_online
        self.settle_ms=settle_ms;self.check_ms=check_ms
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self._step)
        self.active=False;self.original=None;self.changed=False
        self.errors=[];self.queue=[];self.phase=None;self.previous=None;self.attempts=0

    def _ac_online(self):
        root=self.hardware.root/'class/power_supply'
        return any(self.hardware.read(path/'online')=='1' for path in root.glob('*'))

    def start(self):
        if self.active:raise RuntimeError('Calibration is already running')
        self.errors=[];self.changed=False;self.original=None
        if not self.ac_online():self.done.emit('Connect AC power before calibrating.');return
        try:
            original=self.hardware.bridge_read('profile')
            if original is None or int(original) not in dict(MODE_ORDER):
                raise RuntimeError('Current performance mode is unavailable')
            self.original=int(original)
            missing=set(self.calibrator.missing_modes())
            self.queue=[(mode,name) for mode,name in MODE_ORDER if name in missing]
            self.active=True
            self._next_mode()
        except Exception as exc:self._finish(str(exc))

    def _next_mode(self):
        if not self.active:return
        if not self.queue:self._finish('; '.join(self.errors));return
        if not self.ac_online():self._finish('AC power disconnected during calibration.');return
        self.mode,self.name=self.queue.pop(0)
        self.progress.emit('Reading '+self.name+'...')
        self.previous=None;self.attempts=0;self.phase='confirm'
        try:
            self.changed=True
            self.hardware.write('profile',self.mode)
            self.timer.start(self.check_ms)
        except Exception as exc:self._unavailable('mode switch failed: '+str(exc))

    def _unavailable(self,reason):
        self.errors.append(self.name+' ('+reason+')')
        self._next_mode()

    def _step(self):
        if not self.active:return
        try:
            if not self.ac_online():self._finish('AC power disconnected during calibration.');return
            current=self.hardware.bridge_read('profile')
            if self.phase=='confirm':
                self.attempts+=1
                if current==str(self.mode):
                    self.phase='sample';self.attempts=0;self.timer.start(self.settle_ms)
                elif self.attempts<5:self.timer.start(self.check_ms)
                else:self._unavailable('mode not confirmed')
                return
            if current!=str(self.mode):self._unavailable('mode changed during capture');return
            power=self.cpu_power.snapshot()
            fan=self.hardware.bridge_read('fan_mode')
            domains=power.get('domains',{}) if isinstance(power,dict) else {}
            mmio=domains.get('intel-rapl-mmio:0') or domains.get('mmio') or domains.get('intel-rapl:0')
            if not isinstance(mmio,dict) or not self.calibrator._complete(mmio):
                self._unavailable('Intel RAPL limits or Tau unavailable');return
            signature=(power.get('domains'),power.get('boost'),fan)
            self.attempts+=1
            if signature!=self.previous:
                if self.attempts>=34:self._unavailable('RAPL values did not settle');return
                self.previous=copy.deepcopy(signature);self.timer.start(self.check_ms);return
            if self.hardware.bridge_read('profile')!=str(self.mode):
                self._unavailable('mode changed during capture');return
            data=copy.deepcopy(self.base_data)
            data.update(profile=str(self.mode),cpu_power=power,fan_mode=fan,
                        model=self.calibrator.identity.get('model'),
                        bridge=self.hardware.bridge.exists(),cpu_policy_active=False)
            data.pop('custom_fans',None)
            status=self.calibrator.update(data)
            if status.get('error'):self._unavailable(status['error']);return
            if not status.get('ready'):self._unavailable('Incomplete observed profile');return
            self._next_mode()
        except Exception as exc:self._unavailable(str(exc))

    def cancel(self):
        if self.active:self._finish('Calibration cancelled.')

    def _finish(self,error=''):
        self.timer.stop();self.active=False
        if self.changed and self.original is not None:
            try:
                self.hardware.write('profile',self.original)
                if self.hardware.bridge_read('profile')!=str(self.original):
                    raise RuntimeError('restored mode was not confirmed')
            except Exception as exc:error=(error+'; ' if error else '')+'Original mode restore failed: '+str(exc)
        self.progress.emit('Calibration complete.' if not error else 'Calibration incomplete.')
        self.done.emit(error)
