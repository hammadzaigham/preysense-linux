"""Missing-only per-mode RAPL capture using the Windows settle/restore flow.

Profiles captured in one run are held in memory and committed together so a
failed mode does not leave a partial write from that cycle. Already-complete
modes stay untouched. The original Acer mode is always restored at the end.
"""
import copy
from PySide6.QtCore import QObject, QTimer, Signal

MODE_ORDER = ((6, 'Eco'), (0, 'Quiet'), (1, 'Balanced'), (4, 'Performance'), (5, 'Turbo'))
# Match Windows DriverFactoryCalibration.LiveModeSettleMilliseconds.
DEFAULT_SETTLE_MS = 2000


class CalibrationCycle(QObject):
    progress = Signal(str)
    done = Signal(str)

    def __init__(self, hardware, cpu_power, calibrator, base_data=None, parent=None, *,
                 ac_online=None, settle_ms=DEFAULT_SETTLE_MS, check_ms=150):
        super().__init__(parent)
        self.hardware = hardware
        self.cpu_power = cpu_power
        self.calibrator = calibrator
        self.base_data = copy.deepcopy(base_data or {})
        self.ac_online = ac_online or self._ac_online
        self.settle_ms = settle_ms
        self.check_ms = check_ms
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._step)
        self.active = False
        self.original = None
        self.changed = False
        self.errors = []
        self.queue = []
        self.phase = None
        self.previous = None
        self.attempts = 0

    def _ac_online(self):
        root = self.hardware.root / 'class/power_supply'
        return any(self.hardware.read(path / 'online') == '1' for path in root.glob('*'))

    def start(self):
        if self.active:
            raise RuntimeError('Calibration is already running')
        self.errors = []
        self.changed = False
        self.original = None
        if not self.ac_online():
            self.done.emit('Plug in AC power before calibrating.')
            return
        try:
            original = self.hardware.bridge_read('profile')
            if original is None or int(original) not in dict(MODE_ORDER):
                raise RuntimeError('Could not read the current performance mode.')
            self.original = int(original)
            missing = set(self.calibrator.missing_modes())
            self.queue = [(mode, name) for mode, name in MODE_ORDER if name in missing]
            if not self.queue:
                self.done.emit('')
                return
            self.calibrator.begin_batch()
            self.active = True
            self._next_mode()
        except Exception as exc:
            self._finish(str(exc))

    def _next_mode(self):
        if not self.active:
            return
        if not self.queue:
            self._finish('; '.join(self.errors))
            return
        if not self.ac_online():
            self._finish('AC power was unplugged during calibration.')
            return
        self.mode, self.name = self.queue.pop(0)
        self.progress.emit(f'Reading {self.name}…')
        self.previous = None
        self.attempts = 0
        self.phase = 'confirm'
        try:
            self.changed = True
            self.hardware.write('profile', self.mode)
            self.timer.start(self.check_ms)
        except Exception as exc:
            self._unavailable(f'could not switch mode ({exc})')

    def _unavailable(self, reason):
        self.errors.append(f'{self.name}: {reason}')
        self._next_mode()

    def _step(self):
        if not self.active:
            return
        try:
            if not self.ac_online():
                self._finish('AC power was unplugged during calibration.')
                return
            current = self.hardware.bridge_read('profile')
            if self.phase == 'confirm':
                self.attempts += 1
                if current == str(self.mode):
                    self.phase = 'sample'
                    self.attempts = 0
                    self.timer.start(self.settle_ms)
                elif self.attempts < 5:
                    self.timer.start(self.check_ms)
                else:
                    self._unavailable('mode did not stick after switching')
                return
            if current != str(self.mode):
                self._unavailable('mode changed during capture')
                return
            power = self.cpu_power.snapshot()
            fan = self.hardware.bridge_read('fan_mode')
            domains = power.get('domains', {}) if isinstance(power, dict) else {}
            mmio = domains.get('intel-rapl-mmio:0') or domains.get('mmio') or domains.get('intel-rapl:0')
            if not isinstance(mmio, dict) or not self.calibrator._complete(mmio):
                self._unavailable('could not read CPU power limits')
                return
            signature = (power.get('domains'), power.get('boost'), fan)
            self.attempts += 1
            if signature != self.previous:
                if self.attempts >= 34:
                    self._unavailable('CPU limits did not settle')
                    return
                self.previous = copy.deepcopy(signature)
                self.timer.start(self.check_ms)
                return
            if self.hardware.bridge_read('profile') != str(self.mode):
                self._unavailable('mode changed during capture')
                return
            boost = power.get('boost') if isinstance(power.get('boost'), bool) else None
            try:
                self.calibrator.stage_profile(self.name, mmio.get('pl1'), mmio.get('pl2'), mmio.get('tau'), boost)
            except ValueError as exc:
                self._unavailable(str(exc))
                return
            self._next_mode()
        except Exception as exc:
            self._unavailable(str(exc))

    def cancel(self):
        if self.active:
            self._finish('Calibration cancelled.')

    def _restore_original(self):
        if not self.changed or self.original is None:
            return None
        last_error = None
        for _ in range(5):
            try:
                self.hardware.write('profile', self.original)
                if self.hardware.bridge_read('profile') == str(self.original):
                    return None
                last_error = 'restored mode was not confirmed'
            except Exception as exc:
                last_error = str(exc)
            # Brief poll gap without blocking the GUI thread for long.
            self.timer.stop()
        return last_error or 'could not restore the original mode'

    def _finish(self, error=''):
        self.timer.stop()
        self.active = False
        restore_error = self._restore_original()
        lowered = (error or '').lower()
        # Cancel / AC loss drops uncommitted samples. Successful modes in a mixed
        # run are still committed so missing-only retries can resume.
        abort_batch = lowered.startswith('calibration cancelled') or 'unplugged' in lowered
        if abort_batch:
            self.calibrator.discard_batch()
        else:
            try:
                status = self.calibrator.commit_batch()
                if status.get('error'):
                    error = (error + '; ' if error else '') + status['error']
            except Exception as exc:
                error = (error + '; ' if error else '') + str(exc)
                self.calibrator.discard_batch()
        if restore_error:
            error = (error + '; ' if error else '') + f'Could not restore the original mode ({restore_error}).'
        self.progress.emit('Calibration complete.' if not error else 'Calibration incomplete.')
        self.done.emit(error)
