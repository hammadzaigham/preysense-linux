"""Unselected telemetry must not touch its sensor transports."""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpu_telemetry import CpuTelemetry
class DemandTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.sensor=CpuTelemetry(Path(self.temp.name))
 def test_empty_request_reads_no_sensors(self):
  with patch.object(self.sensor,'frequencies') as f,patch.object(self.sensor,'hybrid_cpus') as h,patch.object(self.sensor,'core_usage') as u,patch.object(self.sensor,'power_w') as p,patch.object(self.sensor,'memory_used_gb') as m:
   data=self.sensor.snapshot(set())
   for method in (f,h,u,p,m):method.assert_not_called()
  self.assertTrue(all(value is None for value in data.values()))
 def test_memory_only_avoids_other_sensors(self):
  with patch.object(self.sensor,'frequencies') as f,patch.object(self.sensor,'core_usage') as u,patch.object(self.sensor,'power_w') as p,patch.object(self.sensor,'memory_used_gb',return_value=7.5) as m:
   data=self.sensor.snapshot({'memory_used_gb'})
   for method in (f,u,p):method.assert_not_called()
   m.assert_called_once()
  self.assertEqual(data['memory_used_gb'],7.5)
 def test_group_frequency_only_does_not_read_usage(self):
  with patch.object(self.sensor,'frequencies',return_value={0:3000,1:1500}),patch.object(self.sensor,'hybrid_cpus',return_value=({0},{1})),patch.object(self.sensor,'core_usage') as usage:
   data=self.sensor.snapshot({'cpu_p_core_mhz'})
   usage.assert_not_called()
  self.assertEqual(data['cpu_p_core_mhz'],3000)
  self.assertIsNone(data['cpu_e_core_mhz'])
 def test_pausing_sampling_resets_delta_baselines(self):
  self.sensor.previous=('package',1,100,0);self.sensor.cpu_previous={0:(1,2,3,4)};self.sensor.cpu_previous_time=0
  self.sensor.snapshot(set())
  self.assertIsNone(self.sensor.previous);self.assertEqual(self.sensor.cpu_previous,{})
if __name__=='__main__':unittest.main()
