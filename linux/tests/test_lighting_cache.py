import sys,tempfile,unittest,errno
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hardware import Hardware

class LightingCacheTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.h=Hardware(Path(self.temp.name));self.node=Path(self.temp.name)/'hid';self.node.touch()
 def tearDown(self):self.h.close_lighting();self.temp.cleanup()
 def test_keyboard_and_logo_share_handle(self):
  with patch.object(self.h,'hid_device',return_value=self.node) as discover,patch('hardware.fcntl.ioctl') as ioctl:
   self.h.lighting([(1,2,3)]*4,75);first=self.h._hid_device
   self.h.logo_lighting((1,2,3),75);self.h.lighting([(2,3,4)]*4,75)
  self.assertIs(first,self.h._hid_device);discover.assert_called_once();self.assertEqual(ioctl.call_count,9)
  self.h.close_lighting();self.assertTrue(first.closed)
 def test_disconnection_reopens_once_and_replays_packet_set(self):
  with patch.object(self.h,'hid_device',return_value=self.node) as discover,patch('hardware.fcntl.ioctl',side_effect=[OSError(errno.ENODEV,'disconnected'),None,None,None,None]) as ioctl:
   self.h.lighting([(1,2,3)]*4,75)
  self.assertEqual(discover.call_count,2);self.assertEqual(ioctl.call_count,5)
 def test_permission_failure_does_not_retry(self):
  with patch.object(self.h,'hid_device',return_value=self.node) as discover,patch('hardware.fcntl.ioctl',side_effect=PermissionError(errno.EPERM,'denied')):
   with self.assertRaises(PermissionError):self.h.lighting([(1,2,3)]*4,75)
  discover.assert_called_once();self.assertIsNone(self.h._hid_device)
