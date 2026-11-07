import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from hotkeys import Hotkeys
class HotkeyEventsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.native=self.root/'devices/platform/preysense';self.native.mkdir(parents=True)
  for name,value in [('predator_events','0'),('shortcut_events','0 0 0')]: (self.native/name).write_text(value)
 def tearDown(self):self.temp.cleanup()
 def test_older_driver_keeps_compatible_fallback(self):
  keys=Hotkeys(root=self.root)
  try:self.assertTrue(keys.timer.isActive());self.assertIsNone(keys.event_poll)
  finally:keys.stop()
 def test_notification_driver_has_no_periodic_timer_and_acknowledges_counters(self):
  (self.native/'event_notifications').write_text('1')
  epoll=Mock();epoll.fileno.return_value=0
  with patch('hotkeys.select.epoll',return_value=epoll),patch('hotkeys.QSocketNotifier') as notifier:
   keys=Hotkeys(root=self.root)
   try:
    self.assertFalse(keys.timer.isActive());self.assertEqual(epoll.register.call_count,2)
    toggles=[];keys.predator.connect(lambda:toggles.append(True))
    (self.native/'predator_events').write_text('1');epoll.poll.return_value=[(1,2)];keys.event_ready()
    self.assertEqual(toggles,[True])
    self.assertEqual(keys.counter('predator_events'),'1')
   finally:keys.stop()
  epoll.close.assert_called_once()
 def test_regular_file_cannot_fake_notification_support(self):
  (self.native/'event_notifications').write_text('1')
  keys=Hotkeys(root=self.root)
  try:self.assertTrue(keys.timer.isActive());self.assertEqual(keys.event_fds,{})
  finally:keys.stop()
