"""OEM-mode mapping ownership and confirmation; never writes a live profile."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from system_power import SystemPower,MODE_TARGETS
class Client:
    def __init__(self):self.name=':1.10';self.profile='balanced';self.writes=[];self.fail=False;self.ignore=False
    def owner(self):return self.name
    def active_profile(self):return self.profile
    def set_profile(self,p):
        self.writes.append(p)
        if self.fail:raise RuntimeError('Denied')
        if not self.ignore:self.profile=p
class SystemPowerTests(unittest.TestCase):
    def setUp(self):self.c=Client();self.s=SystemPower(self.c)
    def test_mapping_startup_and_confirmed_transitions(self):
        for mode,target in MODE_TARGETS.items():self.s.sync(mode);self.assertEqual(self.c.profile,target)
        self.assertTrue(self.s.snapshot()['owned'])
    def test_same_confirmed_mode_does_not_fight_manual_kde_change(self):
        self.s.sync('Turbo');self.c.profile='balanced';self.s.sync('5');self.s.sync(5)
        self.assertEqual(self.c.writes,['performance']);self.assertFalse(self.s.snapshot()['owned'])
        self.s.shutdown();self.assertEqual(self.c.profile,'balanced')
    def test_restores_original_only_while_still_owned(self):
        self.s.sync(6);self.s.sync(4);self.s.shutdown()
        self.assertEqual(self.c.profile,'balanced');self.assertFalse(self.s.snapshot()['owned'])
    def test_external_change_before_shutdown_preserved(self):
        self.s.sync(6);self.c.profile='performance';self.s.shutdown()
        self.assertEqual(self.c.writes,['power-saver']);self.assertEqual(self.c.profile,'performance')
    def test_failed_set_not_retried_on_same_mode_new_transition_retries(self):
        self.c.fail=True
        for _ in range(5):self.s.sync(6)
        self.assertEqual(self.c.writes,['power-saver']);self.assertIsNotNone(self.s.snapshot()['error'])
        self.c.fail=False;self.s.sync(0);self.assertEqual(self.c.writes,['power-saver','power-saver'])
    def test_readback_mismatch_not_claimed_owned(self):
        self.c.ignore=True;self.s.sync(5)
        self.assertFalse(self.s.snapshot()['owned']);self.assertIsNotNone(self.s.snapshot()['error'])
    def test_restart_attempts_once_and_never_restores_old_daemon_baseline(self):
        self.s.sync(6);self.c.name=':1.11';self.c.profile='performance';self.s.sync(6);self.s.sync(6)
        self.assertEqual(self.c.writes,['power-saver','power-saver'])
        self.s.shutdown();self.assertEqual(self.c.profile,'performance')
    def test_invalid_does_not_contact_backend(self):
        for v in (None,True,3,'Unknown'):self.s.sync(v)
        self.assertEqual(self.c.writes,[])
if __name__=='__main__':unittest.main()
