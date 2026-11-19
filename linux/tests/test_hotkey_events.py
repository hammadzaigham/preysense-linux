import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from hotkeys import Hotkeys, classify_report
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
 def test_keyboard_brightness_counter_reports_signed_changes_without_startup_step(self):
  counter = self.native/'keyboard_brightness_steps'
  counter.write_text('-3')
  keys = Hotkeys(root=self.root)
  try:
   changes = []
   keys.keyboard_brightness.connect(changes.append)
   keys.poll()
   counter.write_text('-2')
   keys.poll()
   counter.write_text('-4')
   keys.poll()
   self.assertEqual(changes, [1, -2])
  finally:keys.stop()
 def test_acer_vendor_brightness_reports(self):
  self.assertEqual(classify_report(bytes.fromhex('04 7c ff')), 'brightness_up')
  self.assertEqual(classify_report(bytes.fromhex('04 7d ff')), 'brightness_down')
  self.assertIsNone(classify_report(bytes.fromhex('04 7c 00')))
  self.assertIsNone(classify_report(bytes.fromhex('a0 7d ff')))
 def test_hid_brightness_deduplicates_repeats_and_standard_input(self):
  keys = Hotkeys(root=self.root)
  try:
   changes = []
   keys.keyboard_brightness.connect(changes.append)
   with patch('hotkeys.time.monotonic', side_effect=[1, 1.01, 1.02, 1.03, 1.2]):
    keys.dispatch_brightness(1, 'hid')
    keys.dispatch_brightness(1, 'hid')
    keys.dispatch_brightness(1, 'evdev')
    keys.dispatch_brightness(-1, 'hid')
    keys.dispatch_brightness(-1, 'evdev')
   self.assertEqual(changes, [1, -1, -1])
  finally:keys.stop()
