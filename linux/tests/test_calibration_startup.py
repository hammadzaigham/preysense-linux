import json,os,sys,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibration import Calibrator

class StartupCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'calibration.json'
        dmi=self.root/'class/dmi/id';dmi.mkdir(parents=True)
        for name,value in (('sys_vendor','Acer'),('product_name','Test model'),('bios_version','1.0')):(dmi/name).write_text(value)
        self.data={'model':'Test model','profile':'1','fan_mode':'1 1',
                   'cpu_power':{'domains':{'intel-rapl-mmio:0':{'pl1':65.,'pl2':140.,'tau':55.967744}}}}
    def tearDown(self):self.temp.cleanup()
    def test_missing_profiles_require_consent(self):
        calibrator=Calibrator(self.path,self.root);self.assertFalse(calibrator.has_profile())
        calibrator.update(self.data);self.assertTrue(Calibrator(self.path,self.root).has_profile())
    def test_corrupt_or_empty_profile_requires_consent(self):
        self.path.write_text('bad JSON');self.assertFalse(Calibrator(self.path,self.root).has_profile())
        self.path.unlink();calibrator=Calibrator(self.path,self.root);calibrator.update({'model':'Test model','profile':'255'})
        self.assertFalse(calibrator.has_profile())
    def test_mmio_limits_saved_and_missing_values_fill(self):
        calibrator=Calibrator(self.path,self.root);calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Balanced'],{'pl1':65.,'pl2':140.,'tau':55.967744})
        self.data['cpu_power']['domains']['intel-rapl-mmio:0']={'pl1':85.,'pl2':140.,'tau':55.967744}
        calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Balanced']['pl1'],65.)
        self.data['profile']='5';calibrator.update(self.data)
        self.assertEqual(calibrator.cache['Turbo']['pl1'],85.)
    def test_missing_or_nonfinite_driver_values_are_not_guessed(self):
        self.data['cpu_power']['domains']['intel-rapl-mmio:0']={'pl1':float('nan'),'pl2':0,'tau':55.967744}
        calibrator=Calibrator(self.path,self.root);calibrator.update(self.data)
        self.assertNotIn('Balanced',calibrator.cache)
    def test_worker_starts_cycle_on_queued_calibration_command(self):
        from preysense import Worker
        worker=Mock();worker.calibration_enabled=False
        Worker.command(worker,'calibrate',True)
        worker.begin_calibration.assert_called_once();worker.hardware.write.assert_not_called();worker.poll.assert_not_called()
    def test_startup_later_and_accept_only_emit_on_accept(self):
        from preysense import Window
        owner=Mock();owner._calibration_needed=True;owner.quitting=False
        with patch('calibration_ui.confirm_calibration',return_value=False):Window.prompt_startup_calibration(owner)
        owner.command.emit.assert_not_called();self.assertTrue(owner._calibration_needed)
        with patch('calibration_ui.confirm_calibration',return_value=True),patch('calibration_ui.run_calibration',return_value=True) as run:
            Window.prompt_startup_calibration(owner)
        run.assert_called_once_with(owner);self.assertFalse(owner._calibration_needed)
    def test_real_modal_has_later_and_calibrate(self):
        from PySide6.QtWidgets import QApplication,QWidget,QPushButton
        from PySide6.QtCore import QTimer
        from calibration_ui import confirm_calibration
        app=QApplication.instance() or QApplication([]);owner=QWidget();seen=[]
        def later():
            modal=app.activeModalWidget();seen.append([b.text() for b in modal.findChildren(QPushButton)]);modal.reject()
        QTimer.singleShot(0,later)
        self.assertFalse(confirm_calibration(owner));self.assertIn('Later',seen[0]);self.assertIn('Calibrate Now',seen[0])

if __name__=='__main__':unittest.main()
