"""Power-source change notifications from kernel uevents, with no polling.

The worker still decides which source is active. This object only coalesces
power-supply events into a notification, without reading firmware or sysfs.
"""
import errno
import socket
from PySide6.QtCore import QObject, Signal, QTimer, QSocketNotifier


def power_supply_event(payload):
    """Accept bounded kernel power-supply changes, including adapter hotplug."""
    if not isinstance(payload, bytes) or len(payload) > 65536:
        return False
    fields = {}
    for item in payload.split(b'\0'):
        if b'=' in item:
            key, value = item.split(b'=', 1)
            fields[key] = value
    return (fields.get(b'SUBSYSTEM') == b'power_supply' and
            fields.get(b'ACTION') in (b'add', b'change', b'remove'))


class PowerEvents(QObject):
    changed = Signal()

    def __init__(self, parent=None, *, connect=True):
        super().__init__(parent)
        self.socket = None
        self.notifier = None
        self.error = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.changed)
        if connect:
            self.start()

    @property
    def available(self):
        return self.socket is not None

    def start(self):
        if self.socket is not None:
            return
        connection = None
        try:
            connection = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM,
                                       getattr(socket, 'NETLINK_KOBJECT_UEVENT', 15))
            connection.setblocking(False)
            # Port ID zero asks the kernel for a unique ID; group 1 is uevents.
            connection.bind((0, 1))
            self.socket = connection
            self.notifier = QSocketNotifier(connection.fileno(), QSocketNotifier.Read, self)
            self.notifier.activated.connect(self.read_ready)
            self.error = None
        except OSError as exc:
            if connection is not None:
                connection.close()
            self.socket = None
            self.error = str(exc)

    def feed(self, payload, sender_pid=0):
        """Ignore userspace senders; multiple events share one short debounce."""
        if sender_pid == 0 and power_supply_event(payload) and not self.timer.isActive():
            self.timer.start()

    def read_ready(self, *_):
        if self.socket is None:
            return
        # Yield after a bounded batch rather than monopolizing the GUI thread.
        for _ in range(64):
            try:
                payload, sender = self.socket.recvfrom(65536)
                self.feed(payload, sender[0])
            except BlockingIOError:
                return
            except OSError as exc:
                if exc.errno == errno.ENOBUFS:
                    # A dropped event needs one source resync, never a poll loop.
                    if not self.timer.isActive():
                        self.timer.start()
                    return
                self.error = str(exc)
                self.close()
                return

    def close(self):
        self.timer.stop()
        if self.notifier is not None:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.socket is not None:
            self.socket.close()
            self.socket = None
