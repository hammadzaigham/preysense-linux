"""Missing-only factory capture cache with Windows-shaped profile fields.

Profiles are buffered during a calibration cycle and committed together so a
failed mid-cycle capture does not leave a half-written file from that run.
"""
from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows dev hosts
    fcntl = None

MODES = {0: 'Quiet', 1: 'Balanced', 4: 'Performance', 5: 'Turbo', 6: 'Eco'}
MAX_BYTES = 262144


def _number(value, maximum):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum else None


def _profile_from_values(values):
    if not isinstance(values, dict):
        return None
    pl1 = _number(values.get('CpuPl1Watts', values.get('pl1')), 2000)
    pl2 = _number(values.get('CpuPl2Watts', values.get('pl2')), 2000)
    tau = _number(values.get('CpuTurboTimeLimitSeconds', values.get('tau')), 4000000)
    if pl1 is None or pl2 is None or tau is None:
        return None
    if pl1 < 5 or pl2 < pl1:
        return None
    boost = values.get('CpuBoost', values.get('boost'))
    boost_mode = values.get('CpuBoostMode')
    if boost_mode is None and isinstance(boost, bool):
        boost_mode = 1 if boost else 0
    profile = {
        'CpuPl1Watts': int(round(float(pl1))),
        'CpuPl2Watts': int(round(float(pl2))),
        'CpuTurboTimeLimitSeconds': int(round(float(tau))),
        'CpuBoost': boost if isinstance(boost, bool) else None,
        'CpuBoostMode': boost_mode if isinstance(boost_mode, int) else None,
        # Legacy aliases used by older Linux CPU policy helpers.
        'pl1': float(pl1),
        'pl2': float(pl2),
        'tau': float(tau),
    }
    for src, dst in (
        ('GpuPowerOffsetWatts', 'GpuPowerOffsetWatts'),
        ('GpuDynamicBoostWatts', 'GpuDynamicBoostWatts'),
        ('PlatformPowerOffsetWatts', 'PlatformPowerOffsetWatts'),
        ('ct', 'GpuPowerOffsetWatts'),
        ('db', 'GpuDynamicBoostWatts'),
        ('cp', 'PlatformPowerOffsetWatts'),
    ):
        raw = values.get(src)
        if type(raw) in (int, float) and raw == int(raw) and 0 <= raw <= 255:
            profile[dst] = int(raw)
    return profile


class Calibrator:
    def __init__(self, path=None, root=Path('/sys'), config_store=None):
        base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        self.path = Path(path) if path is not None else base / 'PreySense' / 'calibration.json'
        self.root = Path(root)
        self.config_store = config_store
        self.identity = self._read_identity()
        self.cache, self.corrupt = self._load()
        self._pending = {}

    def _read_identity(self):
        dmi = self.root / 'class/dmi/id'
        if not dmi.exists():
            dmi = self.root / 'devices/virtual/dmi/id'
        identity = {}
        for key, name in (('vendor', 'sys_vendor'), ('model', 'product_name'), ('bios', 'bios_version')):
            try:
                identity[key] = (dmi / name).read_text().strip()
            except OSError:
                identity[key] = ''
        return identity

    def _load(self):
        # Prefer unified preysense.json FactoryDefaults when available.
        if self.config_store is not None:
            factory = self.config_store.data.get('Tuning', {}).get('FactoryDefaults', {})
            if isinstance(factory, dict) and factory:
                valid = {}
                for mode_name, values in factory.items():
                    profile = _profile_from_values(values)
                    if mode_name in MODES.values() and profile:
                        valid[mode_name] = profile
                if valid:
                    return valid, False
        try:
            if self.path.is_symlink():
                raise ValueError('Calibration symlink is not accepted')
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError('Calibration too large')
            data = json.loads(self.path.read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            if not isinstance(data, dict):
                raise ValueError('Calibration schema')
            valid = {}
            for mode_name, values in data.items():
                profile = _profile_from_values(values)
                if mode_name in MODES.values() and profile:
                    valid[mode_name] = profile
            return valid, False
        except FileNotFoundError:
            return {}, False
        except (OSError, ValueError, UnicodeError, RecursionError):
            return {}, True

    @staticmethod
    def _mode(value):
        if value in MODES.values():
            return value
        if type(value) is int:
            return MODES.get(value)
        if isinstance(value, str) and value.isdigit():
            return MODES.get(int(value))
        return None

    @staticmethod
    def _complete(profile):
        return _profile_from_values(profile) is not None

    def _status(self, mode, count=0, written=False, error=None):
        ready = bool(mode and self._complete(self.cache.get(mode)))
        return dict(
            state='ready' if ready else 'partial',
            ready=ready,
            newfilled=count,
            written=written,
            current_profile=mode,
            missing_profiles=[name for name in ('Eco', 'Quiet', 'Balanced', 'Performance', 'Turbo')
                              if not self._complete(self.cache.get(name))],
            error=error,
        )

    def has_profile(self):
        return any(self._complete(p) for p in self.cache.values())

    def missing_modes(self):
        return [name for name in ('Eco', 'Quiet', 'Balanced', 'Performance', 'Turbo')
                if not self._complete(self.cache.get(name))]

    def needs_calibration(self):
        return bool(self.missing_modes())

    def begin_batch(self):
        self._pending = {}

    def stage_profile(self, mode_name, pl1, pl2, tau, boost=None, gpu=None):
        values = {
            'CpuPl1Watts': pl1, 'CpuPl2Watts': pl2, 'CpuTurboTimeLimitSeconds': tau, 'CpuBoost': boost,
        }
        if isinstance(gpu, dict):
            if gpu.get('ct') is not None:
                values['GpuPowerOffsetWatts'] = gpu['ct']
            if gpu.get('db') is not None:
                values['GpuDynamicBoostWatts'] = gpu['db']
            if gpu.get('cp') is not None:
                values['PlatformPowerOffsetWatts'] = gpu['cp']
        profile = _profile_from_values(values)
        if not profile:
            raise ValueError(f'{mode_name} CPU limits are incomplete')
        self._pending[mode_name] = profile
        return profile

    def discard_batch(self):
        self._pending = {}

    def commit_batch(self):
        """Atomically merge pending profiles into cache + JSON. Empty pending is a no-op."""
        if not self._pending:
            return self._status(None)
        try:
            return self._write_merged(self._pending)
        finally:
            self._pending = {}

    def update(self, data):
        """Immediate single-mode update (legacy / opportunistic). Prefer batch during cycles."""
        if not isinstance(data, dict):
            return self._status(None)
        mode = self._mode(data.get('profile'))
        if not mode:
            return self._status(None)
        if self._complete(self.cache.get(mode)):
            return self._status(mode)
        power = data.get('cpu_power') if isinstance(data.get('cpu_power'), dict) else {}
        domains = power.get('domains') if isinstance(power.get('domains'), dict) else {}
        mmio = domains.get('intel-rapl-mmio:0') or domains.get('mmio')
        if not isinstance(mmio, dict):
            mmio = domains.get('intel-rapl:0') if isinstance(domains.get('intel-rapl:0'), dict) else {}
        boost = power.get('boost') if isinstance(power.get('boost'), bool) else None
        profile = _profile_from_values({
            'pl1': mmio.get('pl1'), 'pl2': mmio.get('pl2'), 'tau': mmio.get('tau'), 'boost': boost,
        })
        if not profile:
            return self._status(mode)
        try:
            return self._write_merged({mode: profile})
        except (OSError, ValueError) as exc:
            return self._status(mode, error=str(exc))

    def _write_merged(self, additions):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.path.parent / (self.path.name + '.lock')

        def merge_and_encode():
            latest, corrupt = self._load()
            count = 0
            for mode, profile in additions.items():
                if self._complete(latest.get(mode)):
                    continue
                latest[mode] = profile
                count += 1
            # Persist Windows-shaped fields only.
            serializable = {}
            for name, values in latest.items():
                entry = {
                    'CpuPl1Watts': values['CpuPl1Watts'],
                    'CpuPl2Watts': values['CpuPl2Watts'],
                    'CpuTurboTimeLimitSeconds': values['CpuTurboTimeLimitSeconds'],
                    'CpuBoost': values.get('CpuBoost'),
                    'CpuBoostMode': values.get('CpuBoostMode'),
                }
                for key in ('GpuPowerOffsetWatts', 'GpuDynamicBoostWatts', 'PlatformPowerOffsetWatts'):
                    if values.get(key) is not None:
                        entry[key] = values[key]
                serializable[name] = entry
            encoded = json.dumps(serializable, indent=2, sort_keys=True).encode()
            if len(encoded) > MAX_BYTES:
                raise ValueError('Calibration size limit reached')
            return latest, corrupt, count, encoded, serializable

        def commit_atomic(latest, corrupt, count, encoded, serializable):
            if count == 0:
                self.cache = latest
                return self._status(next(iter(additions), None))
            if corrupt and self.path.exists():
                self.path.replace(self.path.with_name(self.path.name + '.corrupt-' + uuid.uuid4().hex))
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.calibration-', delete=False) as stream:
                    temporary = Path(stream.name)
                    try:
                        os.chmod(temporary, 0o600)
                    except OSError:
                        pass
                    stream.write(encoded)
                    stream.flush()
                    try:
                        os.fsync(stream.fileno())
                    except OSError:
                        pass
                os.replace(temporary, self.path)
                temporary = None
                try:
                    directory = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                except OSError:
                    pass
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self._sync_config_store(serializable)
            self.cache = {name: _profile_from_values(v) for name, v in serializable.items()}
            self.corrupt = False
            return self._status(next(iter(additions), None), count=count, written=True)

        if fcntl is None:
            return commit_atomic(*merge_and_encode())

        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return commit_atomic(*merge_and_encode())

    def _sync_config_store(self, serializable):
        if self.config_store is None:
            return
        try:
            def mutator(cfg):
                cfg.setdefault('Tuning', {})['FactoryDefaults'] = copy.deepcopy(serializable)
            self.config_store.update(mutator)
        except Exception:
            # calibration.json remains authoritative if config sync fails.
            pass
