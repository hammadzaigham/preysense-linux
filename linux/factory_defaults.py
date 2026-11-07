"""Immutable observed CPU defaults, deliberately distinct from proven factory calibration.

Capture never switches modes or writes hardware. Reset targets only the currently
selected mode and uses a validated same-machine snapshot with transactional rollback.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

MODES = {0: 'Quiet', 1: 'Balanced', 4: 'Performance', 5: 'Turbo', 6: 'Eco'}
DOMAIN_NAMES = {'intel-rapl:0', 'intel-rapl-mmio:0'}
IDENTITY_FIELDS = ('vendor', 'product', 'bios')


def machine_identity(root=Path('/sys/class/dmi/id')):
    """Non-secret hardware identity; serial numbers and UUIDs are not stored."""
    root = Path(root)
    return {key: (root / filename).read_text().strip()
            for key, filename in [('vendor', 'sys_vendor'), ('product', 'product_name'),
                                  ('bios', 'bios_version')]}


def validate_identity(identity):
    if not isinstance(identity, dict) or set(identity) != set(IDENTITY_FIELDS):
        raise ValueError('Hardware identity requires vendor, product and BIOS')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in identity.values()):
        raise ValueError('Invalid hardware identity')
    return dict(identity)


def validate_domains(domains):
    if not isinstance(domains, dict) or not domains or not set(domains) <= DOMAIN_NAMES:
        raise ValueError('Observed defaults require known package-0 RAPL domains')
    result = {}
    for name, values in domains.items():
        if not isinstance(values, dict) or set(values) != {'pl1', 'pl2', 'tau'}:
            raise ValueError('Each RAPL domain requires PL1, PL2 and Tau')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
            raise ValueError('RAPL values must be finite numbers')
        if not 5 <= values['pl1'] <= values['pl2'] <= 999 or not 0 < values['tau'] <= 4000000:
            raise ValueError('Observed RAPL values are outside the supported hardware range')
        result[name] = dict(values)
    return result


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


class ObservedDefaults:
    """Write-once per-mode snapshots. They are not evidence of untouched OEM limits."""
    def __init__(self, directory=None, identity=None):
        self.directory = Path(directory or Path.home() / '.local/share/PreySense/observed-defaults')
        self.identity = validate_identity(identity if identity is not None else machine_identity())

    def _path(self, mode):
        if type(mode) is not int or mode not in MODES:
            raise ValueError('Unknown performance mode')
        return self.directory / f'mode-{mode}.json'

    def load(self, mode):
        path = self._path(mode)
        if path.is_symlink():
            raise RuntimeError('Observed defaults must not be a symlink')
        if path.stat().st_size > 65536:
            raise ValueError('Observed-defaults file is unexpectedly large')
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {'snapshot', 'sha256'}:
            raise ValueError('Invalid observed-defaults envelope')
        snapshot = data['snapshot']
        if _digest(snapshot) != data['sha256']:
            raise ValueError('Observed-defaults integrity check failed')
        required = {'schema', 'identity', 'mode', 'captured_at', 'origin', 'factory_verified', 'domains', 'boost'}
        if not isinstance(snapshot, dict) or set(snapshot) != required or snapshot['schema'] != 1:
            raise ValueError('Unknown observed-defaults schema')
        if validate_identity(snapshot['identity']) != self.identity or type(snapshot['mode']) is not int or snapshot['mode'] != mode:
            raise ValueError('Observed defaults belong to another machine, BIOS or mode')
        if snapshot['origin'] != 'observed-live-linux' or snapshot['factory_verified'] is not False:
            raise ValueError('Observed defaults must not claim factory verification')
        if type(snapshot['boost']) not in (bool, type(None)):
            raise ValueError('Invalid captured CPU boost state')
        if not isinstance(snapshot['captured_at'], str):
            raise ValueError('Missing capture timestamp')
        validate_domains(snapshot['domains'])
        return snapshot

    def status(self):
        result = {}
        for mode, name in MODES.items():
            try:
                snapshot = self.load(mode)
                result[str(mode)] = dict(mode=name, available=True, captured_at=snapshot['captured_at'],
                                         factory_verified=False, domains=snapshot['domains'])
            except FileNotFoundError:
                result[str(mode)] = dict(mode=name, available=False, error='Not captured')
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                result[str(mode)] = dict(mode=name, available=False, error=str(exc))
        return result

    def capture_snapshot(self, mode, domains, boost=True):
        """Save a validated snapshot for mode directly (e.g. from startup baseline)."""
        path = self._path(mode)
        if path.exists() or path.is_symlink():
            return self.load(mode)
        validated = validate_domains(domains)
        snapshot = dict(schema=1, identity=self.identity, mode=mode,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        origin='observed-live-linux', factory_verified=False,
                        domains=validated, boost=boost)
        envelope = dict(snapshot=snapshot, sha256=_digest(snapshot))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tempname = tempfile.mkstemp(prefix='.capture-', dir=self.directory)
        temporary = Path(tempname)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(_encoded(envelope) + b'\n'); stream.flush(); os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o400)
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return self.load(mode)

    def capture(self, mode, power, current_mode, *, controller_active=False):
        """Read a stable current-mode baseline; never overwrite an existing capture.

        current_mode is a callable reading firmware, not a cached UI selection.
        The caller must stop its saved custom CPU policies before capture.
        That does not establish that another process or firmware did not tune limits.
        """
        path = self._path(mode)
        if controller_active:
            raise RuntimeError('Stop custom CPU policies before capturing observed defaults')
        if path.exists() or path.is_symlink():
            raise FileExistsError('This mode already has an immutable observed-defaults capture')
        if current_mode() != mode:
            raise RuntimeError('Select the requested mode before capturing observed defaults')
        first = validate_domains(power.capture())
        boost = power.boost()
        if type(boost) not in (bool, type(None)):
            raise ValueError('Invalid CPU boost readback')
        second = validate_domains(power.capture())
        if first != second or power.boost() != boost or current_mode() != mode:
            raise RuntimeError('Mode or CPU limits changed during capture; no defaults were saved')
        snapshot = dict(schema=1, identity=self.identity, mode=mode,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        origin='observed-live-linux', factory_verified=False,
                        domains=first, boost=boost)
        envelope = dict(snapshot=snapshot, sha256=_digest(snapshot))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise RuntimeError('Observed-defaults directory must not be a symlink')
        # A complete fsynced temporary file is linked with no-overwrite semantics.
        # Failed/interrupted writes never expose partial JSON as the immutable file.
        fd, tempname = tempfile.mkstemp(prefix='.capture-', dir=self.directory)
        temporary = Path(tempname)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(_encoded(envelope) + b'\n'); stream.flush(); os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o400)
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return self.load(mode)

    def reset(self, mode, power, current_mode, *, controller_active=False):
        """Explicitly restore captured CPU values with rollback on any error.

        No saved policy is deleted by this class. The caller must stop/remove the
        selected custom policy first or it could reapply on the next worker poll.
        """
        snapshot = self.load(mode)
        if controller_active:
            raise RuntimeError('Stop custom CPU policies before restoring observed defaults')
        if current_mode() != mode:
            raise RuntimeError('Observed defaults can restore only the currently active mode')
        before = validate_domains(power.capture())
        if set(before) != set(snapshot['domains']):
            raise RuntimeError('RAPL domain layout changed; refusing a partial defaults reset')
        boost = power.boost()
        if current_mode() != mode:
            raise RuntimeError('Mode changed before reset; no CPU values were written')
        try:
            power.restore(snapshot['domains'])
            if current_mode() != mode:
                raise RuntimeError('Firmware mode changed during defaults reset')
            if snapshot['boost'] is not None:
                power.set_boost(snapshot['boost'])
            actual = validate_domains(power.capture())
            if actual != snapshot['domains'] or current_mode() != mode:
                raise RuntimeError('Observed-defaults reset readback failed or firmware mode changed')
            if snapshot['boost'] is not None and power.boost() != snapshot['boost']:
                raise RuntimeError('Observed-defaults CPU boost readback failed')
        except Exception as exc:
            if current_mode() != mode:
                raise RuntimeError(f'{exc}; firmware mode changed, so rollback was skipped to preserve its new policy') from exc
            errors = []
            try:
                power.restore(before)
            except Exception as rollback:
                errors.append(str(rollback))
            if boost is not None:
                try:
                    power.set_boost(boost)
                except Exception as rollback:
                    errors.append(str(rollback))
            if errors:
                raise RuntimeError(f'{exc}; defaults reset rollback failed: {"; ".join(errors)}') from exc
            raise
        return snapshot
