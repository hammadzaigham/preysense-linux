"""Synchronize confirmed OEM modes with the native Linux power-profile service."""
from PySide6.QtCore import QObject
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusReply, QDBusVariant

SERVICE = 'org.freedesktop.UPower.PowerProfiles'
PATH = '/org/freedesktop/UPower/PowerProfiles'
INTERFACE = SERVICE
MODE_TARGETS = {0:'power-saver', 1:'balanced', 4:'performance', 5:'performance', 6:'power-saver'}
MODE_NAMES = {'Quiet':0, 'Balanced':1, 'Performance':4, 'Turbo':5, 'Eco':6}
PROFILES = frozenset(MODE_TARGETS.values())


def normalize_mode(mode):
    if isinstance(mode, str):
        if mode in MODE_NAMES: return MODE_NAMES[mode]
        try: mode = int(mode)
        except ValueError: return None
    return mode if type(mode) is int and mode in MODE_TARGETS else None


class PowerProfilesClient:
    def __init__(self):
        self.bus = QDBusConnection.systemBus()

    def owner(self):
        if not self.bus.isConnected(): raise RuntimeError('System bus unavailable')
        reply = self.bus.interface().serviceOwner(SERVICE)
        if not reply.isValid() or not reply.value():
            raise RuntimeError('Power-profile service unavailable')
        return reply.value()

    def _properties(self):
        interface = QDBusInterface(SERVICE, PATH, 'org.freedesktop.DBus.Properties', self.bus)
        interface.setTimeout(1500)
        return interface

    def active_profile(self):
        reply = QDBusReply(self._properties().call('Get', INTERFACE, 'ActiveProfile'))
        if not reply.isValid(): raise RuntimeError(reply.error().message())
        value = reply.value()
        value = value.variant() if isinstance(value, QDBusVariant) else value
        if value not in PROFILES: raise RuntimeError('Power-profile state unavailable')
        return value

    def set_profile(self, profile):
        if profile not in PROFILES: raise ValueError('Invalid Linux power profile')
        reply = QDBusReply(self._properties().call('Set', INTERFACE, 'ActiveProfile', QDBusVariant(profile)))
        if not reply.isValid(): raise RuntimeError(reply.error().message())


class SystemPower(QObject):
    """Create and call in the worker thread. Constructor never contacts D-Bus.

    A confirmed OEM transition, including first startup snapshot, permits one
    write attempt. Repeated snapshots only observe and preserve manual choices.
    """
    def __init__(self, client=None, parent=None):
        super().__init__(parent)
        self._client = client
        self.mode = None
        self.target = None
        self.profile = None
        self.available = None
        self.error = None
        self.service_owner = None
        self.attempted = None
        self.previous = None
        self.last_written = None
        self.owned_owner = None

    @property
    def client(self):
        if self._client is None: self._client = PowerProfilesClient()
        return self._client

    def _forget_ownership(self):
        self.previous = None
        self.last_written = None
        self.owned_owner = None

    def sync(self, mode):
        mode = normalize_mode(mode)
        if mode is None: return self.snapshot()
        self.mode = mode
        self.target = MODE_TARGETS[mode]
        read_ok = False
        try:
            owner = self.client.owner()
            if self.service_owner != owner:
                self._forget_ownership()
                self.service_owner = owner
            current = self.client.active_profile()
            self.available = True
            self.profile = current
            read_ok = True
            if self.last_written is not None and current != self.last_written:
                self._forget_ownership()
            key = (owner, mode)
            if self.attempted == key:
                return self.snapshot()
            self.attempted = key  # Failed requests retry only after a real transition/restart.
            self.error = None
            if current == self.target:
                return self.snapshot()
            previous = self.previous if self.last_written is not None else current
            self.client.set_profile(self.target)
            actual = self.client.active_profile()
            self.profile = actual
            if actual != self.target:
                self._forget_ownership()
                raise RuntimeError('Linux power-profile readback did not confirm the requested profile')
            self.previous = previous
            self.last_written = actual
            self.owned_owner = owner
        except (RuntimeError, ValueError, TypeError) as exc:
            self.error = str(exc)
            # A readable profile may still exist even if a Set is rejected.
            if not read_ok:
                self.available = False
                self.profile = None
        return self.snapshot()

    def snapshot(self):
        return dict(mode=self.mode, target=self.target, profile=self.profile,
                    available=self.available, owned=self.last_written is not None,
                    error=self.error)

    def shutdown(self):
        try:
            if self.last_written is not None:
                owner = self.client.owner()
                current = self.client.active_profile()
                self.profile = current
                if owner == self.owned_owner and current == self.last_written:
                    self.client.set_profile(self.previous)
                    self.profile = self.client.active_profile()
                    if self.profile != self.previous:
                        raise RuntimeError('Linux power-profile restoration was not confirmed')
                self._forget_ownership()
                self.error = None
        except (RuntimeError, ValueError, TypeError) as exc:
            self.error = str(exc)
        return self.snapshot()
