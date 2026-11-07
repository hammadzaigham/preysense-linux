import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from telemetry_demand import demand
class DemandTests(unittest.TestCase):
 def test_hidden_overlay_has_no_sensor_demand(self):self.assertEqual(demand({'visible':False,'cpu':['Power'],'gpu':['Usage']}),(set(),set()))
 def test_custom_fans_only_add_temperature(self):self.assertEqual(demand({},True),({'cpu_temp'},{'temperature'}))
 def test_visible_slots_map_exactly_and_fan_rpm_is_ec(self):self.assertEqual(demand({'visible':True,'cpu':['Power'],'gpu':['Fan Speed','Memory']}),({'cpu_power_w','gpu_fan'},{'memory_used_gb','memory_total_gb'}))
 def test_calibration_does_not_add_gpu_reference(self):self.assertEqual(demand({},False),(set(),set()))

class SamplingTests(unittest.TestCase):
 def test_burst_poll_does_not_read_sensors_or_append_snapshots(self):
  from unittest.mock import Mock,patch
  from preysense import Worker
  w=Mock();w.last_sensor_poll=10;w.state_dirty=False
  with patch('preysense.time.monotonic',return_value=10.2):Worker.poll(w)
  w.hardware.snapshot.assert_not_called();w.snapshot.emit.assert_not_called()
 def test_empty_cpu_demand_skips_ec_temperature_and_fans(self):
  import tempfile
  from unittest.mock import patch
  from hardware import Hardware
  with tempfile.TemporaryDirectory() as folder:
   h=Hardware(Path(folder))
   with patch.object(h,'bridge_read',return_value=None) as read:
    h.snapshot(requested=set())
   queried={c.args[0] for c in read.call_args_list}
   self.assertFalse(queried & {'cpu_temp','gpu_temp','cpu_fan','gpu_fan'})
   h.close_lighting()

class SamplingTimerTests(unittest.TestCase):
 def test_hidden_overlay_stops_timer_even_when_custom_fan_timer_runs(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  from preysense import Worker
  timer=Mock();fan=Mock();fan.isActive.return_value=False
  owner=SimpleNamespace(timer=timer,fan_timer=fan,curve=object(),overlay_demand={'visible':False,'cpu':{'Power'},'gpu':{'Usage'}})
  Worker.update_sampling_timers(owner)
  timer.stop.assert_called_once();timer.start.assert_not_called();fan.start.assert_called_once_with(1000)
 def test_no_overlay_or_custom_fans_stops_both_timers(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  from preysense import Worker
  owner=SimpleNamespace(timer=Mock(),fan_timer=Mock(),curve=None,overlay_demand={'visible':False})
  Worker.update_sampling_timers(owner)
  owner.timer.stop.assert_called_once();owner.fan_timer.stop.assert_called_once()
 def test_hide_command_stops_overlay_timer_before_any_poll(self):
  from unittest.mock import Mock
  from preysense import Worker
  owner=Mock();owner.calibration_cycle=None
  Worker.command(owner,'overlay_metrics',{'visible':False})
  owner.timer.stop.assert_called_once();owner.fan_timer.stop.assert_not_called()
