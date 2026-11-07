import sys,random,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lighting_effects import SOFTWARE_EFFECTS,frame
from lighting_animation import LightingAnimation
from hardware import Hardware
from PySide6.QtCore import QCoreApplication,QObject,Signal

class EffectTests(unittest.TestCase):
 def test_every_effect_is_four_bounded_rgb_zones(self):
  rng=random.Random(7)
  for effect in SOFTWARE_EFFECTS:
   for count in range(0,100,3):
    with self.subTest(effect=effect,count=count):
     colors=frame(effect,count*.13,count,rng=rng)
     self.assertEqual(len(colors),4)
     self.assertTrue(all(len(c)==3 and all(type(v) is int and 0<=v<=255 for v in c) for c in colors))
 def test_matrix_head_and_cylon_brush(self):
  self.assertEqual(frame('Matrix Cascade',0,0)[0],(57,255,20))
  self.assertEqual(frame('Cylon Scanner',0,3,(1,2,3))[1],(1,2,3))
 def test_animated_and_unknown_effect(self):
  self.assertNotEqual(frame('Rainbow Cycle',0,0),frame('Rainbow Cycle',1,30))
  with self.assertRaises(ValueError):frame('unknown',0,0)

class LogoTests(unittest.TestCase):
 def test_logo_has_distinct_target_and_mask(self):
  with tempfile.TemporaryDirectory() as temp:
   node=Path(temp)/'hid';node.touch();h=Hardware();self.addCleanup(h.close_lighting)
   with patch.object(h,'hid_device',return_value=node),patch('hardware.fcntl.ioctl') as ioctl:
    h.logo_lighting((10,20,30),80,'Static',10)
    self.assertEqual(ioctl.call_args.args[2],bytes([0xa4,0x83,2,80,5,0,10,20,30,1,0]))
 def test_dynamic_effect_applies_original_luminance_scaling(self):
  with tempfile.TemporaryDirectory() as temp:
   node=Path(temp)/'hid';node.touch();h=Hardware();self.addCleanup(h.close_lighting)
   with patch.object(h,'hid_device',return_value=node),patch('hardware.fcntl.ioctl') as ioctl:
    h.lighting([(100,200,40)]*4,50,'Breathing',5)
    self.assertEqual(ioctl.call_args.args[2][6:9],bytes([50,100,20]))
 def test_logo_average_uses_all_four_zones(self):
  from hardware import average_color
  self.assertEqual(average_color([(100,0,0),(0,100,0),(0,0,100),(100,100,100)]),(50,50,50))
 def test_logo_off_and_keyboard_off_opcode(self):
  with tempfile.TemporaryDirectory() as temp:
   node=Path(temp)/'hid';node.touch();h=Hardware();self.addCleanup(h.close_lighting)
   with patch.object(h,'hid_device',return_value=node),patch('hardware.fcntl.ioctl') as ioctl:
    h.logo_lighting((10,20,30),0)
    self.assertEqual(ioctl.call_args.args[2],bytes([0xa4,0x83,1,0,0,0,0,0,0,1,0]))
    h.lighting([(10,20,30)]*4,0)
    self.assertEqual(ioctl.call_args.args[2][2],2)

class Owner(QObject):
 lighting_frame=Signal(list)
 done=Signal(str,str)
 def __init__(self):
  super().__init__();self.hardware=Mock();self.hardware.bridge_read.side_effect=lambda name:'30' if name=='led_timeout' else '0'

class AnimationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QCoreApplication.instance() or QCoreApplication([])
 def setUp(self):self.owner=Owner();self.animation=LightingAnimation(self.owner)
 def tearDown(self):
  if self.animation.active:self.animation.stop()
 def start(self):self.animation.start(dict(colors=[(40,216,202)]*4,brightness=80,effect='Rainbow Cycle',speed=5))
 def test_stop_restores_native_timeout(self):
  self.start();self.owner.hardware.write.assert_called_with('led_timeout',0)
  self.animation.stop();self.owner.hardware.write.assert_called_with('led_timeout',30)
 def test_stop_restores_synced_logo_to_average_base_color(self):
  self.animation.start(dict(colors=[(100,0,0),(0,100,0),(0,0,100),(100,100,100)],brightness=80,effect='Rainbow Cycle',speed=5,sync_logo=True))
  self.animation.stop();self.owner.hardware.logo_lighting.assert_called_with((50,50,50),80,'Static',5)
 def test_restore_timeout_even_if_hid_write_fails(self):
  self.start();self.owner.hardware.lighting.side_effect=OSError('disconnected')
  with self.assertRaises(OSError):self.animation.stop()
  self.assertFalse(self.animation.active);self.owner.hardware.write.assert_called_with('led_timeout',30)
 def test_idle_timer_slows_and_wake_restores_animation_interval(self):
  self.start();self.animation.started-=31;self.animation.wake_at-=31
  self.owner.hardware.bridge_read.side_effect=lambda name:'35000'
  self.animation.tick();self.assertEqual(self.animation.timer.interval(),200)
  writes=self.owner.hardware.lighting.call_count
  self.animation.tick();self.assertEqual(self.owner.hardware.lighting.call_count,writes)
  self.owner.hardware.bridge_read.side_effect=lambda name:'0'
  self.animation.tick();self.assertEqual(self.animation.timer.interval(),125)
  self.assertEqual(self.owner.hardware.lighting.call_args.args[1],80)
 def test_keyboard_idle_turns_animation_off(self):
  self.start();self.animation.started-=31;self.animation.wake_at-=31;self.owner.hardware.bridge_read.side_effect=lambda name:'35000'
  self.animation.tick();self.assertEqual(self.owner.hardware.lighting.call_args.args[1],0)
if __name__=='__main__':unittest.main()
