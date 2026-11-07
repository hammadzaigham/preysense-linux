import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from setup_audio import setup, install_stereo_daemon
class AudioSetupTests(unittest.TestCase):
 def test_existing_binaries_and_tuning_are_not_downloaded_or_reset(self):
  with tempfile.TemporaryDirectory() as directory:
   home=Path(directory);bindir=home/'.local/bin';bindir.mkdir(parents=True)
   for name in ('acerultrax-cli','acerultrax-daemon'):(bindir/name).touch()
   manifest=home/'.local/share/acerultrax/manifest.toml';manifest.parent.mkdir(parents=True);manifest.write_text('existing calibration')
   with patch('setup_audio.os.geteuid',return_value=1000),patch('setup_audio.Path.home',return_value=home),patch('setup_audio.urllib.request.urlopen') as download,patch('setup_audio.subprocess.run') as run:
    setup();download.assert_not_called()
   calls=[call.args[0][1:] for call in run.call_args_list]
   self.assertEqual(calls,[['--user','try-restart','acerultrax.service'],['detect'],['autostart','on'],['status']]);self.assertEqual(manifest.read_text(),'existing calibration')
 def test_root_audio_setup_rejected(self):
  with patch('setup_audio.os.geteuid',return_value=0):
   with self.assertRaises(SystemExit):setup()

 def test_stereo_backend_upgrade_is_idempotent(self):
  with tempfile.TemporaryDirectory() as directory:
   bindir=Path(directory)
   self.assertTrue(install_stereo_daemon(bindir))
   first=(bindir/'acerultrax-daemon').stat().st_mtime_ns
   self.assertFalse(install_stereo_daemon(bindir))
   self.assertEqual((bindir/'acerultrax-daemon').stat().st_mtime_ns,first)
   self.assertTrue((bindir/'acerultrax-daemon').stat().st_mode & 0o100)
 def test_stereo_backend_checksum_mismatch_keeps_existing_binary(self):
  with tempfile.TemporaryDirectory() as directory:
   bindir=Path(directory);existing=bindir/'acerultrax-daemon';existing.write_text('existing')
   with patch('setup_audio.STEREO_DAEMON_SHA256','invalid'):
    with self.assertRaises(RuntimeError):install_stereo_daemon(bindir)
   self.assertEqual(existing.read_text(),'existing')
