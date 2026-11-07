import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpu_power import CpuPower
from display import Display

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for domain in ('intel-rapl:0','intel-rapl-mmio:0'):
            p=self.root/domain;p.mkdir()
            for name,value in {'name':'package-0','constraint_0_name':'long_term','constraint_1_name':'short_term','constraint_0_power_limit_uw':'65000000','constraint_1_power_limit_uw':'140000000','constraint_0_time_window_us':'56000000'}.items(): (p/name).write_text(value)
        self.power=CpuPower(self.root)
    def tearDown(self): self.temp.cleanup()
    def test_both_domains_updated(self):
        self.power.apply(55,100)
        for values in self.power.snapshot()['domains'].values(): self.assertEqual((values['pl1'],values['pl2']),(55,100))
    def test_restore_preserves_different_domain_defaults(self):
        (self.root/'intel-rapl:0/constraint_0_power_limit_uw').write_text('115000000')
        saved=self.power.capture()
        self.power.apply(55,100)
        self.power.restore(saved)
        values=self.power.snapshot()['domains']
        self.assertEqual(values['intel-rapl:0']['pl1'],115)
        self.assertEqual(values['intel-rapl-mmio:0']['pl1'],65)
    def test_tau_is_applied_and_restored_in_both_domains(self):
        saved=self.power.capture();self.power.apply(55,100,tau=16)
        self.assertTrue(all(v['tau']==16 for v in self.power.capture().values()))
        self.power.restore(saved)
        self.assertTrue(all(v['tau']==56 for v in self.power.capture().values()))
    def test_windows_tau_endpoints_require_verified_unit(self):
        with self.assertRaises(RuntimeError):self.power.apply(45,80,tau=0)
        self.power.time_unit_us=976
        self.power.apply(45,80,tau=0)
        self.assertTrue(all(v['tau']==.001952 for v in self.power.capture().values()))
        self.power.apply(45,80,tau=449)
        self.assertTrue(all(v['tau']==3667902.070784 for v in self.power.capture().values()))
    def test_unsupported_tau_is_rejected_before_writes(self):
        with self.assertRaises(ValueError):self.power.apply(55,100,tau=999)
        self.assertTrue(all(v['pl1']==65 for v in self.power.capture().values()))
    def test_cpu_boost_is_boolean_with_readback(self):
        self.power.boost_path=self.root/'no_turbo';self.power.boost_path.write_text('0')
        self.power.set_boost(False);self.assertEqual(self.power.boost_path.read_text(),'1')
        self.power.set_boost(True);self.assertTrue(self.power.boost())
        with self.assertRaises(ValueError):self.power.set_boost('on')
    def test_startup_values_are_not_application_caps(self):
        self.power.apply(85,140)
        for values in self.power.snapshot()['domains'].values():self.assertEqual(values['pl1'],85)
        self.power.apply(220,250)
        for values in self.power.snapshot()['domains'].values():self.assertEqual(values['pl1'],220)
    def test_failed_second_domain_restores_first(self):
        original=Path.write_text
        def fail_second(path,text,*a,**kw):
            if path.parent.name=='intel-rapl-mmio:0' and text=='55000000': raise PermissionError('locked')
            return original(path,text,*a,**kw)
        with patch.object(Path,'write_text',fail_second):
            with self.assertRaises(PermissionError): self.power.apply(55,100)
        for values in self.power.snapshot()['domains'].values(): self.assertEqual((values['pl1'],values['pl2']),(65,140))

class DisplayTests(unittest.TestCase):
    def test_unknown_mode_never_runs_command(self):
        d=Display()
        with patch.object(d,'snapshot',return_value={'modes':[{'id':'1'}]}),patch('display.subprocess.run') as run:
            with self.assertRaises(ValueError): d.apply('other')
            run.assert_not_called()
if __name__=='__main__': unittest.main()
