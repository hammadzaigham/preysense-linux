import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hotkeys import classify_report,next_mode
from audio import Audio

class HotkeyTests(unittest.TestCase):
 def test_vendor_mode_report(self):
  self.assertEqual(classify_report(bytes([4,0x85,0xff])),'turbo')
  self.assertEqual(classify_report(bytes([4,5,1])),'turbo')
  self.assertIsNone(classify_report(bytes([4,5,0])))
 def test_feature_and_ordinary_reports_never_trigger(self):
  for report in (b'',bytes([0xa0,0x85,0xff]),bytes([1,0x85,0xff]),bytes([4,0x7d,0xff])):self.assertIsNone(classify_report(report))
 def test_predator_vendor_report(self):self.assertEqual(classify_report(bytes([4,0x75,0xff])),'predator')
 def test_firmware_brightness_reports_are_ignored(self):
  for code in (0x7d,0x7c,0x57,0x58,0x7a,0x7b):
   self.assertIsNone(classify_report(bytes([4,code,0xff])))
 def test_ac_and_battery_cycle(self):
  for ac in (True,False):
   self.assertEqual([next_mode(v,ac) for v in (6,0,1,4,5)],[0,1,4,5,6])
   current=6;visited=[]
   for _ in range(5):visited.append(current);current=next_mode(current,ac)
   self.assertEqual(visited,[6,0,1,4,5]);self.assertEqual(current,6)
class AudioTests(unittest.TestCase):
 def test_unknown_command_rejected(self):
  with self.assertRaises(ValueError):Audio().command('arbitrary',{})
 def test_profile_command_encoding(self):
  with patch.object(Audio,'request',return_value=None) as request:
   Audio().command('set-profile',{'name':'Movie'})
   calls = [c.kwargs for c in request.call_args_list]
   self.assertIn({'name':'Movie'}, calls)
   self.assertIn({'name':'Movie','device':'@speakers'}, calls)
   self.assertIn({'name':'Movie','device':'@headphones'}, calls)
 def test_enable_command_encoding(self):
  with patch.object(Audio,'request',return_value=None) as request:
   Audio().command('enable',{'on':True})
   calls = [c.kwargs for c in request.call_args_list]
   self.assertIn({'on':True}, calls)
   self.assertIn({'on':True,'device':'@speakers'}, calls)
   self.assertIn({'on':True,'device':'@headphones'}, calls)

class PredatorFallbackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from PySide6.QtCore import QCoreApplication
  cls.app=QCoreApplication.instance() or QCoreApplication([])
 def setUp(self):
  import tempfile
  from hotkeys import Hotkeys
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.native=self.root/'devices/platform/preysense';self.native.mkdir(parents=True)
  (self.native/'predator_events').write_text('0');(self.native/'predator_down').write_text('0')
  self.now=10.;self.clock=patch('hotkeys.time.monotonic',side_effect=lambda:self.now);self.clock.start()
  self.hotkeys=Hotkeys(root=self.root);self.hotkeys.timer.stop();self.events=[];self.hotkeys.predator.connect(lambda:self.events.append('toggle'))
 def tearDown(self):self.hotkeys.stop();self.clock.stop();self.temp.cleanup()
 def advance(self,seconds):self.now+=seconds
 def test_hid_only_fallback_toggles_immediately(self):
  self.hotkeys.predator_fallback(0);self.assertEqual(self.events,['toggle'])
  self.assertFalse(hasattr(self.hotkeys,'predator_timer'))
 def test_native_hold_suppresses_fallback_for_modifier_combos(self):
  (self.native/'predator_down').write_text('1');self.hotkeys.predator_fallback(0);self.assertEqual(self.events,[])
 def test_native_counter_increment_suppresses_duplicate_fallback(self):
  (self.native/'predator_events').write_text('1');self.hotkeys.predator_fallback(0);self.assertEqual(self.events,[])
 def test_rapid_predator_presses_only_toggle(self):
  sequence=[];turbo=[];self.hotkeys.predator.connect(lambda:sequence.append('toggle'));self.hotkeys.mode.connect(sequence.append);self.hotkeys.turbo.connect(lambda:turbo.append(True))
  self.hotkeys.dispatch('predator');self.assertEqual(sequence,['toggle'])
  self.now+=.2;self.hotkeys.dispatch('predator');self.advance(.5)
  self.assertEqual(sequence,['toggle','toggle']);self.assertEqual(turbo,[])
 def test_second_press_at_400ms_only_toggles(self):
  modes=[];self.hotkeys.mode.connect(modes.append)
  self.now=0.;self.hotkeys.dispatch('predator');self.now=.4;self.hotkeys.dispatch('predator')
  self.assertEqual(modes,[]);self.assertEqual(self.events,['toggle','toggle'])
 def test_after_boundary_two_instant_singles(self):
  self.hotkeys.dispatch('predator');self.assertEqual(self.events,['toggle'])
  self.now+=.401;self.hotkeys.dispatch('predator');self.assertEqual(self.events,['toggle','toggle'])
 def test_no_delayed_single_callback_and_fast_poll_interval(self):
  self.hotkeys.dispatch('predator');self.advance(.2)
  self.assertEqual(self.events,['toggle']);self.assertFalse(hasattr(self.hotkeys,'predator_timer'))
  self.assertEqual(self.hotkeys.timer.interval(),25)
 def test_bounce_does_not_become_double(self):
  modes=[];self.hotkeys.mode.connect(modes.append)
  self.hotkeys.dispatch('predator');self.now+=.03;self.hotkeys.dispatch('predator');self.advance(.401)
  self.assertEqual(self.events,['toggle']);self.assertEqual(modes,[])
 def test_turbo_key_stays_separate(self):
  turbo=[];self.hotkeys.turbo.connect(lambda:turbo.append(True))
  self.hotkeys.dispatch('predator');self.hotkeys.dispatch('turbo');self.now+=.1;self.hotkeys.dispatch('turbo')
  self.assertEqual(turbo,[True]);self.assertEqual(self.events,['toggle'])
 def test_native_and_hid_duplicate_produce_one_single(self):
  (self.native/'predator_events').write_text('1');self.hotkeys.poll();self.hotkeys.predator_fallback(0)
  self.assertEqual(self.events,['toggle'])
 def test_native_counter_batch_does_not_change_mode(self):
  modes=[];self.hotkeys.mode.connect(modes.append)
  (self.native/'predator_events').write_text('2');self.hotkeys.poll()
  self.assertEqual(modes,[]);self.assertEqual(self.events,[])
 def test_stop_and_close_cancel_fallback_and_clear_pair(self):
  for stop in (self.hotkeys.close,self.hotkeys.stop):
   self.now+=1;self.hotkeys.dispatch('predator');self.hotkeys.predator_report();stop()
   self.assertFalse(hasattr(self.hotkeys,'first_predator'));self.assertFalse(self.hotkeys.fallback_timer.isActive())
  self.assertEqual(self.events,['toggle','toggle'])

if __name__=='__main__':unittest.main()
