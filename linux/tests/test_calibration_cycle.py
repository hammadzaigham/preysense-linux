import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from calibration import Calibrator
from calibration_cycle import CalibrationCycle

class Hardware:
    def __init__(self,root):self.root=root;self.bridge=root/'bridge';self.bridge.mkdir();self.mode=1;self.writes=[];self.fail=None
    def bridge_read(self,name):return str(self.mode) if name=='profile' else '1 1'
    def write(self,name,value):
        self.writes.append((name,value))
        if value==self.fail:raise RuntimeError('firmware rejected mode')
        self.mode=value
    @staticmethod
    def read(path):
        try:return path.read_text().strip()
        except OSError:return None

class CpuPower:
    def __init__(self,hardware):self.hardware=hardware;self.calls=0;self.unstable=False
    def snapshot(self):
        self.calls+=1;pl1={6:45,0:45,1:65,4:75,5:85}[self.hardware.mode]
        if self.unstable:pl1+=self.calls%2
        return {'domains':{'intel-rapl:0':{'pl1':115,'pl2':140,'tau':55.967744},'intel-rapl-mmio:0':{'pl1':pl1,'pl2':140,'tau':55.967744}},'ceilings':[65,140],'boost':True,'writable':True,'boost_writable':True}

class CycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        dmi=self.root/'class/dmi/id';dmi.mkdir(parents=True)
        for name,value in (('sys_vendor','Acer'),('product_name','Test model'),('bios_version','1.0')):(dmi/name).write_text(value)
        self.hw=Hardware(self.root);self.power=CpuPower(self.hw);self.cal=Calibrator(self.root/'calibration.json',self.root)
        self.base={'model':'Test model','keyboard':'present','bridge':True}
        self.cycle=CalibrationCycle(self.hw,self.power,self.cal,self.base,ac_online=lambda:True)
        self.errors=[];self.progress=[];self.cycle.done.connect(self.errors.append);self.cycle.progress.connect(self.progress.append)
    def tearDown(self):self.cycle.timer.stop();self.temp.cleanup()
    def drive(self,limit=300):
        for _ in range(limit):
            if not self.cycle.active:return
            self.cycle.timer.stop();self.cycle._step()
        self.fail('Cycle did not terminate')
    def seed(self,mode):
        self.hw.mode=mode;data=dict(self.base,profile=str(mode),cpu_power=self.power.snapshot(),fan_mode='1 1');self.cal.update(data);self.hw.mode=1
    def test_windows_order_settle_and_final_restore(self):
        self.assertTrue(self.cal.needs_calibration());self.cycle.start()
        self.assertEqual(self.cycle.timer.interval(),150)
        self.cycle.timer.stop();self.cycle._step()
        self.assertEqual(self.cycle.timer.interval(),2000)
        self.drive()
        self.assertEqual(self.hw.writes,[('profile',6),('profile',0),('profile',1),('profile',4),('profile',5),('profile',1)])
        self.assertEqual(self.errors,['']);self.assertFalse(self.cycle.active);self.assertEqual(self.hw.mode,1)
        self.assertFalse(self.cal.needs_calibration())
        profiles=self.cal.cache
        self.assertEqual(profiles['Turbo']['CpuPl1Watts'],85)
        self.assertEqual(profiles['Turbo']['CpuPl2Watts'],140)
    def test_existing_modes_and_values_never_replaced(self):
        self.seed(6);before=self.cal.cache['Eco'].copy()
        self.cycle.start();self.drive()
        self.assertNotIn(('profile',6),self.hw.writes)
        self.assertEqual(self.cal.cache['Eco'],before)
    def test_failed_mode_is_not_saved_and_original_restored(self):
        self.hw.fail=4;self.cycle.start();self.drive()
        self.assertEqual(self.hw.mode,1);self.assertIn('Performance',self.errors[0]);self.assertEqual(self.cal.missing_modes(),['Performance'])
    def test_cancel_restores_original_without_saving_unsettled_mode(self):
        self.cycle.start();self.cycle.cancel()
        self.assertFalse(self.cycle.active);self.assertEqual(self.hw.mode,1);self.assertEqual(len(self.cal.cache),0)
        self.assertEqual(self.errors,['Calibration cancelled.'])
    def test_ac_required_and_disconnect_restores(self):
        self.cycle.ac_online=lambda:False;self.cycle.start();self.assertFalse(self.hw.writes)
        self.errors.clear();self.cycle.ac_online=lambda:True;self.cycle.start();self.cycle.ac_online=lambda:False;self.cycle._step()
        self.assertEqual(self.hw.mode,1);self.assertTrue('unplugged' in self.errors[0] or 'disconnected' in self.errors[0])
    def test_unstable_samples_are_not_saved(self):
        self.power.unstable=True;self.cycle.start();self.drive()
        self.assertEqual(self.hw.mode,1);self.assertEqual(len(self.cal.cache),0);self.assertIn('did not settle',self.errors[0])

if __name__=='__main__':unittest.main()
