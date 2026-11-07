import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from power_events import PowerEvents, power_supply_event

EVENT = b'change@/devices/platform/AC/power_supply/AC\0ACTION=change\0SUBSYSTEM=power_supply\0POWER_SUPPLY_ONLINE=0\0'


class PowerEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_parser_filters_unrelated_or_invalid_events(self):
        self.assertTrue(power_supply_event(EVENT))
        self.assertTrue(power_supply_event(EVENT.replace(b'ACTION=change', b'ACTION=remove')))
        for data in (b'', 'not bytes', b'x' * 65537,
                     EVENT.replace(b'power_supply\0', b'drm\0'),
                     EVENT.replace(b'ACTION=change', b'ACTION=bind')):
            self.assertFalse(power_supply_event(data))

    def test_multiple_kernel_events_emit_once_without_polling(self):
        watcher = PowerEvents(connect=False)
        calls = []
        watcher.changed.connect(lambda: calls.append(True))
        self.assertFalse(watcher.timer.isActive())
        watcher.feed(EVENT, sender_pid=123)
        self.assertFalse(watcher.timer.isActive())
        for _ in range(10):
            watcher.feed(EVENT)
        QTest.qWait(150)
        self.assertEqual(calls, [True])
        self.assertFalse(watcher.timer.isActive())
        QTest.qWait(120)
        self.assertEqual(calls, [True])
        watcher.close()

    def test_close_cancels_pending_notification(self):
        watcher = PowerEvents(connect=False)
        calls = []
        watcher.changed.connect(lambda: calls.append(True))
        watcher.feed(EVENT)
        watcher.close()
        QTest.qWait(150)
        self.assertEqual(calls, [])

    def test_unavailable_netlink_does_not_add_polling_fallback(self):
        with patch('power_events.socket.socket', side_effect=PermissionError('blocked')):
            watcher = PowerEvents()
        self.assertFalse(watcher.available)
        self.assertFalse(watcher.timer.isActive())
        self.assertIn('blocked', watcher.error)
        watcher.close()


if __name__ == '__main__':
    unittest.main()
