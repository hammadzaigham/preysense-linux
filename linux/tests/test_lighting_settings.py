import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from lighting_settings import startup_lighting
class LightingSettingsTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.s=QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.IniFormat)
 def tearDown(self):self.temp.cleanup()
 def test_first_launch_does_not_invent_saved_lighting(self):self.assertEqual(startup_lighting(self.s),[])
 def test_saved_hardware_and_independent_logo_are_replayed(self):
  self.s.setValue('effect','Wave');self.s.setValue('colors',['#010203']*4);self.s.setValue('brightness',75);self.s.setValue('logo_effect','Breathing');self.s.setValue('logo_color','#aabbcc');self.s.setValue('logo_speed',7)
  commands=startup_lighting(self.s);self.assertEqual([c[0] for c in commands],['lighting','logo_lighting']);self.assertEqual(commands[0][1]['colors'],[(1,2,3)]*4);self.assertEqual(commands[1][1]['color'],(170,187,204));self.assertEqual(commands[1][1]['speed'],7)
 def test_logo_sync_does_not_replay_independent_logo_after_keyboard(self):
  self.s.setValue('effect','Rainbow Cycle');self.s.setValue('logo_effect','Neon');self.s.setValue('sync_logo',True)
  commands=startup_lighting(self.s);self.assertEqual(len(commands),1);self.assertTrue(commands[0][1]['sync_logo'])
 def test_timeout_replays_before_software_animation(self):
  self.s.setValue('led_timeout',30);self.s.setValue('effect','Rainbow Cycle')
  commands=startup_lighting(self.s)
  self.assertEqual(commands[0],('led_timeout',30));self.assertEqual(commands[1][0],'lighting')
 def test_timeout_off_is_saved_and_invalid_timeout_rejected(self):
  self.s.setValue('led_timeout',0);self.assertEqual(startup_lighting(self.s),[('led_timeout',0)])
  self.s.setValue('led_timeout',121)
  with self.assertRaises(ValueError):startup_lighting(self.s)
 def test_invalid_saved_report_is_rejected(self):
  self.s.setValue('effect','Static');self.s.setValue('colors',['not-a-color']*4)
  with self.assertRaises(ValueError):startup_lighting(self.s)
if __name__=='__main__':unittest.main()
