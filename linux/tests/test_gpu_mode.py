import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gpu_mode import GpuMode, requires_confirmation
from hardware import Hardware


class GpuModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gpu = GpuMode(self.root)
        self.gpu.endpoint.parent.mkdir(parents=True)
        self.gpu.endpoint.write_text('3')

    def device(self, driver='nvidia', runtime='suspended'):
        p = self.root/'bus/pci/devices/0000:01:00.0'
        p.mkdir(parents=True)
        for name, value in [('class', '0x030000'), ('vendor', '0x10de'), ('power/runtime_status', runtime)]:
            target = p/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value)
        if driver:
            target = self.root/'bus/pci/drivers'/driver
            target.mkdir(parents=True)
            (p/'driver').symlink_to(target)

    def test_confirmation_boundary(self):
        modes = ('Auto', 'Hybrid', 'NVIDIA GPU Only')
        for current in modes:
            for requested in modes:
                expected = current != requested and 'NVIDIA GPU Only' in (current, requested)
                self.assertEqual(requires_confirmation(current, requested), expected)
        self.assertTrue(requires_confirmation(None, 'NVIDIA GPU Only'))

    def test_cancel_does_not_stage_and_auto_hybrid_never_prompts(self):
        from preysense import Window
        window = Mock()
        window.gpu_tiles = {}
        window._gpu_firmware_mode = 'Hybrid'
        with patch('ui_controls.confirm_gpu_mode', return_value=False) as confirm:
            Window.stage_gpu_mode(window, 'NVIDIA GPU Only')
            window.apply.assert_not_called()
            confirm.assert_called_once()
            confirm.reset_mock()
            Window.stage_gpu_mode(window, 'Auto')
            confirm.assert_not_called()
            window.apply.assert_called_once_with('gpu_mode', 'Auto')
        window.apply.reset_mock()
        window._gpu_firmware_mode = 'NVIDIA GPU Only'
        with patch('ui_controls.confirm_gpu_mode', return_value=True) as confirm:
            Window.stage_gpu_mode(window, 'Hybrid')
            confirm.assert_called_once()
            window.apply.assert_called_once_with('gpu_mode', 'Hybrid')

    def test_real_modal_opens_and_cancel_is_safe(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication,QWidget,QDialog,QLabel,QPushButton
        from PySide6.QtCore import QTimer
        from ui_controls import confirm_gpu_mode
        app=QApplication.instance() or QApplication([])
        parent=QWidget()
        seen=[]
        def cancel():
            dialog=app.activeModalWidget()
            seen.append(dialog)
            self.assertIsNotNone(dialog)
            self.assertEqual(dialog.width(),440)
            self.assertIn('Would you like to switch to NVIDIA GPU Only mode and restart now?',
                          [w.text() for w in dialog.findChildren(QLabel)])
            self.assertIn('Apply && Restart Now',[w.text() for w in dialog.findChildren(QPushButton)])
            dialog.reject()
        QTimer.singleShot(0,cancel)
        self.assertFalse(confirm_gpu_mode(parent,'NVIDIA GPU Only'))
        self.assertEqual(len(seen),1)

    def test_restart_only_after_confirmed_successful_write(self):
        from preysense import Window
        for name,error,pending,expected in (
            ('GPU boot setting: saved','',True,True),
            ('gpu_mode','write failed',True,False),
            ('GPU boot setting: saved','',False,False)):
            window=Mock();window._gpu_restart_pending=pending
            with patch('subprocess.run') as run:
                run.return_value.returncode=0
                Window.finished(window,name,error)
                self.assertEqual(run.called,expected)
                if expected:run.assert_called_once_with(['systemctl','reboot'],capture_output=True,text=True)
            self.assertFalse(window._gpu_restart_pending)

    def test_oem_enum_and_unsupported_modes(self):
        self.device()
        for name, value in [('Hybrid', '1'), ('NVIDIA GPU Only', '2'), ('Auto', '3')]:
            self.assertIn('Restart', self.gpu.stage(name))
            self.assertEqual(self.gpu.endpoint.read_text(), value)
        for name in ('Advanced Optimus', 'iGPU Only', '../../profile', 1):
            with self.assertRaises(ValueError): self.gpu.stage(name)

    def test_unknown_firmware_or_missing_endpoint_disables_writes(self):
        self.gpu.endpoint.write_text('255')
        with self.assertRaises(RuntimeError): self.gpu.stage('Auto')
        self.gpu.endpoint.unlink()
        self.assertFalse(self.gpu.snapshot()['writable'])

    def test_discrete_requires_bound_driver(self):
        self.device(driver=None)
        with self.assertRaises(RuntimeError): self.gpu.stage('NVIDIA GPU Only')
        self.assertIn('Restart', self.gpu.stage('Hybrid'))

    def test_failed_readback_is_not_success(self):
        with patch.object(self.gpu, 'read', return_value='3'):
            with self.assertRaisesRegex(RuntimeError, 'readback'): self.gpu.stage('Hybrid')

    def test_suspended_gpu_never_runs_nvidia_smi(self):
        self.device()
        hardware = Hardware(self.root)
        with patch('hardware.subprocess.run') as run:
            state = hardware.gpu_snapshot()
        run.assert_not_called()
        self.assertEqual(state['status'], 'Sleeping')

    def test_unknown_power_state_never_runs_nvidia_smi(self):
        self.device(runtime='')
        hardware = Hardware(self.root)
        with patch('hardware.subprocess.run') as run: hardware.gpu_snapshot()
        run.assert_not_called()

    def test_panel_and_firmware_reported_separately(self):
        connector = self.root/'class/drm/card1-eDP-1'
        connector.mkdir(parents=True)
        (connector/'enabled').write_text('enabled')
        card = self.root/'class/drm/card1/device'
        card.mkdir(parents=True)
        (card/'vendor').write_text('0x8086')
        self.gpu.endpoint.write_text('2')
        state = self.gpu.snapshot()
        self.assertEqual(state['firmware'], 'NVIDIA GPU Only')
        self.assertEqual(state['panel'], 'Intel')
        self.assertFalse(state['live_switching'])

    def test_worker_routes_gpu_mode_and_failure(self):
        from preysense import Worker
        worker = Worker()
        worker.gpu_mode = Mock()
        worker.poll = Mock()
        worker.gpu_mode.stage.return_value = 'Restart required'
        events = []
        worker.done.connect(lambda name, error: events.append((name, error)))
        worker.command('gpu_mode', 'Hybrid')
        worker.gpu_mode.stage.assert_called_once_with('Hybrid')
        self.assertEqual(events[-1], ('GPU boot setting: Restart required', ''))
        worker.gpu_mode.stage.side_effect = RuntimeError('Firmware rejected write')
        worker.command('gpu_mode', 'Auto')
        self.assertIn('rejected', events[-1][1])

    def test_window_stage_gpu_mode_emits_command(self):
        from preysense import Window
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        window = Window()
        calls = []
        window.command.connect(lambda name, val: calls.append((name, val)))
        window.stage_gpu_mode('Hybrid')
        self.assertEqual(calls, [('gpu_mode', 'Hybrid')])
        window.thread.quit()
        window.thread.wait()


if __name__ == '__main__': unittest.main()
