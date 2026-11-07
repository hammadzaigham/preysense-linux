import os,sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import service_lifecycle as life
class LifecycleTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_manual_launch_and_quit_use_only_fixed_helpers(self):
  config=self.root/'config';config.write_text(json.dumps({'uid':os.getuid()}));marker=self.root/'running'
  with patch.object(life,'CONFIG',config),patch.object(life,'marker',return_value=marker),patch.object(life.subprocess,'run') as run:
   self.assertTrue(life.start_helpers());self.assertTrue(marker.exists())
   self.assertEqual(run.call_args.args[0],['systemctl','--no-ask-password','start',*life.UNITS])
   life.stop_helpers();self.assertFalse(marker.exists())
   self.assertEqual(run.call_args.args[0],['systemctl','--no-ask-password','stop',*life.UNITS])
 def test_failed_start_removes_marker(self):
  config=self.root/'config';config.write_text(json.dumps({'uid':os.getuid()}));marker=self.root/'running'
  with patch.object(life,'CONFIG',config),patch.object(life,'marker',return_value=marker),patch.object(life.subprocess,'run',side_effect=RuntimeError('denied')):
   with self.assertRaises(RuntimeError):life.start_helpers()
  self.assertFalse(marker.exists())
 def test_unconfigured_install_or_other_user_does_not_start_services(self):
  config=self.root/'config'
  with patch.object(life,'CONFIG',config),patch.object(life.subprocess,'run') as run:
   self.assertFalse(life.start_helpers());config.write_text(json.dumps({'uid':os.getuid()+1}));self.assertFalse(life.start_helpers());run.assert_not_called()
