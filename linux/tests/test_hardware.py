import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hardware import Hardware

class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.h = Hardware(self.root)
        self.h.bridge.mkdir(parents=True)
    def tearDown(self): self.h.close_lighting();self.temp.cleanup()
    def test_ram_speed_is_unavailable_when_firmware_cannot_be_read(self):
        from types import SimpleNamespace
        with patch('hardware.Path.is_file',return_value=False),patch('hardware.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='')):
            self.assertIsNone(self.h._detect_ram_speed())

    def test_reject_arbitrary_control(self):
        for name,value in [('profile',255),('fan_mode',2),('battery_limit',50),('../../anything',1)]:
            with self.assertRaises(ValueError): self.h.write(name,value)
    def test_readback_mismatch_is_failure(self):
        with patch.object(self.h,'bridge_read',return_value='5'):
            with self.assertRaises(RuntimeError): self.h.write('profile',1)
    def test_missing_bridge_and_gpu_are_supported(self):
        self.h.bridge.rmdir()
        data = self.h.snapshot()
        self.assertFalse(data['bridge'])
        self.assertIsNone(data['cpu_temp'])
        with patch('hardware.shutil.which',return_value=None):
            self.assertIn('unavailable',self.h.gpu_snapshot()['status'])
    def test_active_gpu_clock_and_memory_measurements(self):
        from types import SimpleNamespace
        gpu=dict(vendor='0x10de',driver='nvidia',runtime='active')
        with patch('gpu_mode.GpuMode.devices',return_value=[gpu]),patch('hardware.shutil.which',return_value='/usr/bin/nvidia-smi'),patch('hardware.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='NVIDIA GPU, 62, 0, 23.5, 1200, 6000, 1024, 8192\n')) as run:
            state=self.h.gpu_snapshot()
        self.assertEqual(state['clock'],'1200')
        self.assertEqual(state['memory_clock_mhz'],'6000')
        self.assertEqual(state['memory_used_gb'],1)
        self.assertEqual(state['memory_total_gb'],8)
        self.assertEqual(state['usage'],'0')
        self.assertIn('clocks.gr',run.call_args.args[0][1])

    def test_idle_controls_are_cached_until_explicit_refresh(self):
        with patch.object(self.h,'bridge_read',return_value='1') as read:
            first=self.h.snapshot(requested=set());count=read.call_count
            self.h.snapshot(requested=set())
            self.assertEqual(read.call_count,count)
            self.assertNotIn('lcd_overdrive',{c.args[0] for c in read.call_args_list})
            self.h.refresh_controls();self.h.snapshot(requested=set())
            self.assertGreater(read.call_count,count)

    def test_empty_gpu_demand_never_opens_driver_or_spawns_tools(self):
        with patch('hardware.subprocess.run') as run,patch('gpu_mode.GpuMode.devices') as devices:
            state=self.h.gpu_snapshot(set())
        run.assert_not_called();devices.assert_not_called();self.assertIn('Idle',state['status'])

    def test_nvidia_default_power_is_reference_not_maximum(self):
        from types import SimpleNamespace
        gpu=dict(vendor='0x10de',driver='nvidia',runtime='active')
        for default,maximum,expected in [('85','140',85.0),('N/A','140',None),('nan','140',None)]:
            line=f'NVIDIA GPU, 62, 0, 23.5, 1200, 6000, 1024, 8192, {default}, {maximum}\n'
            with patch('gpu_mode.GpuMode.devices',return_value=[gpu]),patch('hardware.shutil.which',return_value='/usr/bin/nvidia-smi'),patch('hardware.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=line)):
                state=self.h.gpu_snapshot()
            self.assertEqual(state['default_power_limit_w'],expected)
            self.assertEqual(state['max_power_limit_w'],140.0)

    def test_lighting_packet_matches_windows_protocol(self):
        target = self.root/'keyboard'
        target.touch()
        with patch.object(self.h,'hid_device',return_value=target), patch('hardware.fcntl.ioctl') as call:
            self.h.lighting([(10,20,30)]*4,80)
        self.assertEqual(call.call_count,4)
        self.assertEqual(call.call_args_list[0].args[1],0xc00b4806)
        self.assertEqual(call.call_args_list[0].args[2],bytes([0xa4,0x21,2,80,0,0,10,20,30,1,0]))
        self.assertEqual(call.call_args_list[3].args[2][-2],8)
    def test_invalid_lighting_does_not_open_device(self):
        with patch.object(self.h,'hid_device') as device:
            with self.assertRaises(ValueError): self.h.lighting([(0,0,0)]*4,101)
            device.assert_not_called()

if __name__=='__main__': unittest.main()
