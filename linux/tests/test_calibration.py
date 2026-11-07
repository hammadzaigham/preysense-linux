import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibration import Calibrator,MAX_BYTES

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'user/calibration.json'
        dmi=self.root/'class/dmi/id';dmi.mkdir(parents=True)
        for name,value in (('sys_vendor','Acer'),('product_name','Test model'),('bios_version','1.0')):(dmi/name).write_text(value)
        self.data=dict(model='Test model',profile='1',bridge=True,keyboard='/dev/hidraw0',fan_mode='1 1',cpu_temp='90',cpu_fan='5000',serial='secret',
                       cpu_power=dict(domains={'intel-rapl-mmio:0':dict(pl1=65,pl2=140,tau=56)},ceilings=[65,140],boost=False,writable=False,boost_writable=False),
                       audio=dict(available=False),gpu_mode=dict(available=False))
        self.calibrator=Calibrator(self.path,self.root)
    def tearDown(self):self.temp.cleanup()
    def test_current_mode_only_and_no_dynamic_or_secret_fields(self):
        status=self.calibrator.update(self.data);self.assertTrue(status['ready']);self.assertTrue(status['written']);self.assertGreater(status['newfilled'],0)
        self.assertEqual(set(self.calibrator.cache),{'Balanced'})
        text=self.path.read_text()
        for forbidden in ('cpu_temp','cpu_fan','serial','secret','/dev/hidraw0','intel-rapl:0'):self.assertNotIn(forbidden,text)
    def test_complete_snapshot_cheap_and_preserves_valid_values(self):
        self.calibrator.update(self.data);before=self.path.read_bytes();self.data['cpu_power']['domains']['intel-rapl-mmio:0']['pl1']=50
        with patch.object(self.calibrator,'_load',side_effect=AssertionError('complete cache read')):
            status=self.calibrator.update(self.data)
        self.assertFalse(status['written']);self.assertEqual(status['newfilled'],0);self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.calibrator.cache['Balanced']['pl1'],65)
    def test_missing_only_backfill_and_natural_mode_visit(self):
        self.data['cpu_power']['domains']['intel-rapl-mmio:0']['tau']=None
        self.assertFalse(self.calibrator.update(self.data)['ready'])
        self.data['cpu_power']['domains']['intel-rapl-mmio:0'].update(tau=56,pl2=140)
        self.assertTrue(self.calibrator.update(self.data)['ready']);self.assertEqual(self.calibrator.cache['Balanced']['pl2'],140)
        self.data['profile']='5';self.calibrator.update(self.data);self.assertEqual(set(self.calibrator.cache),{'Balanced','Turbo'})
    def test_no_identity_or_valid_data_no_cache_files(self):
        self.assertFalse(self.calibrator.update({})['written']);self.assertFalse(self.path.exists())
    def test_corrupt_and_oversize_cache_backed_up_then_recovered(self):
        self.path.parent.mkdir()
        for bad in ('{broken','x'*(MAX_BYTES+1)):
            self.path.write_text(bad);calibrator=Calibrator(self.path,self.root);status=calibrator.update(self.data)
            self.assertTrue(status['written']);self.assertTrue(any(p.read_text()==bad for p in self.path.parent.glob('*.corrupt-*')))
    def test_no_valid_new_value_no_rewrite_and_partial_retries(self):
        self.data['cpu_power']['domains']={};status=self.calibrator.update(self.data);self.assertFalse(status['ready'])
        self.assertFalse(self.path.exists())
        self.data['cpu_power']['domains']={'intel-rapl-mmio:0':dict(pl1=40,pl2=80,tau=56)}
        self.assertTrue(self.calibrator.update(self.data)['ready'])
    def test_atomic_replace_failure_keeps_existing_results_and_cleans_temp(self):
        self.calibrator.update(self.data);before=self.path.read_bytes();self.data['profile']='0'
        with patch('calibration.os.replace',side_effect=OSError('fixture failure')):status=self.calibrator.update(self.data)
        self.assertFalse(status['written']);self.assertIn('fixture failure',status['error']);self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(list(self.path.parent.glob('.calibration-*')))
    def test_two_instances_merge_without_overwriting_each_other(self):
        other=Calibrator(self.path,self.root);self.calibrator.update(self.data)
        otherdata=copy.deepcopy(self.data);otherdata['profile']='6';other.update(otherdata)
        self.assertEqual(set(self.calibrator.cache)|set(other.cache),{'Balanced','Eco'})
    def test_nonfinite_unknown_domain_and_invalid_mode_not_captured(self):
        self.data['profile']='255';self.data['cpu_power']['domains']={'unknown':dict(pl1=50,pl2=80,tau=56),'intel-rapl-mmio:0':dict(pl1=float('nan'),pl2=-1,tau=float('inf'))}
        self.calibrator.update(self.data);self.assertEqual(self.calibrator.cache,{})
if __name__=='__main__':unittest.main()
