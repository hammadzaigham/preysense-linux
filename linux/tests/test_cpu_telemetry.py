import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpu_telemetry import CpuTelemetry

class CpuTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.now=0.
        self.procroot=self.root/'proc';self.procroot.mkdir()
        self.sensor=CpuTelemetry(self.root,clock=lambda:self.now,procroot=self.procroot)
        self.domain=self.root/'class/powercap/intel-rapl:0';self.domain.mkdir(parents=True)
        (self.domain/'name').write_text('package-0');(self.domain/'max_energy_range_uj').write_text('1000000000');self.energy(100000000)
    def tearDown(self):self.temp.cleanup()
    def energy(self,value):(self.domain/'energy_uj').write_text(str(value))
    def test_frequency_is_mean_of_readable_kernel_scaling_values(self):
        for index,value in [(0,1500000),(1,2500000),(2,0),(3,-2),(4,999999999)]:
            path=self.root/f'devices/system/cpu/cpu{index}/cpufreq';path.mkdir(parents=True);(path/'scaling_cur_freq').write_text(str(value))
        self.assertEqual(self.sensor.frequency_mhz(),2000)
    def test_real_delta_and_first_sample_unavailable(self):
        self.assertIsNone(self.sensor.power_w());self.now=1.;self.energy(125500000)
        self.assertEqual(self.sensor.power_w(),25.5)
    def test_counter_wrap_uses_documented_range(self):
        self.energy(990000000);self.assertIsNone(self.sensor.power_w())
        self.now=1.;self.energy(15000000);self.assertEqual(self.sensor.power_w(),25)
    def test_invalid_or_missing_counter_resets_baseline(self):
        self.sensor.power_w();(self.domain/'energy_uj').unlink();self.now=1.;self.assertIsNone(self.sensor.power_w())
        self.energy(120000000);self.now=2.;self.assertIsNone(self.sensor.power_w())
        self.energy(130000000);self.now=3.;self.assertEqual(self.sensor.power_w(),10)
    def test_long_or_nonpositive_intervals_have_no_fabricated_value(self):
        self.sensor.power_w();self.energy(110000000);self.assertIsNone(self.sensor.power_w())
        self.now=10.;self.energy(120000000);self.assertIsNone(self.sensor.power_w())
        self.now=11.;self.energy(130000000);self.assertEqual(self.sensor.power_w(),10)
    def test_counter_range_change_resets_baseline(self):
        self.sensor.power_w();self.now=1.;(self.domain/'max_energy_range_uj').write_text('2000000000');self.energy(120000000)
        self.assertIsNone(self.sensor.power_w())
    def test_zero_or_implausible_power_is_unavailable(self):
        self.sensor.power_w();self.now=1.;self.assertIsNone(self.sensor.power_w())
        self.now=1.000001;self.energy(200000000);self.assertIsNone(self.sensor.power_w())
    def test_missing_sysfs_is_read_only_and_unavailable(self):
        missing=self.root/'missing';sensor=CpuTelemetry(missing,procroot=missing)
        self.assertTrue(all(value is None for key,value in sensor.snapshot().items() if not key.endswith("_status")));self.assertFalse(missing.exists())
    def write(self,path,text):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    def topology(self):
        self.write('bus/event_source/devices/cpu_core/cpus','0-1')
        self.write('bus/event_source/devices/cpu_atom/cpus','2,3')
        self.write('devices/system/cpu/online','0-3')
        for index,value in enumerate((3000000,4000000,1500000,2500000)):
            self.write(f'devices/system/cpu/cpu{index}/cpufreq/scaling_cur_freq',str(value))
    def stat(self,values):
        # guest time is already counted in user; these last counters must not be added.
        (self.procroot/'stat').write_text('cpu 999 0 0 1 0 0 0 0 0 0\n'+''.join(f'cpu{i} {busy} 0 0 {idle} {wait} 0 0 0 99 0\n' for i,(busy,idle,wait) in values.items()))
    def test_hybrid_frequency_actual_pmu_lists_and_first_usage_unavailable(self):
        self.topology();self.stat({i:(10,90,0) for i in range(4)})
        data=self.sensor.snapshot()
        self.assertEqual(data['cpu_p_core_mhz'],3500);self.assertEqual(data['cpu_e_core_mhz'],2000)
        self.assertIsNone(data['cpu_p_core_usage']);self.assertIsNone(data['cpu_max_core_usage'])
        self.now=1;self.stat({0:(30,170,0),1:(50,150,0),2:(110,90,0),3:(10,180,10)})
        data=self.sensor.snapshot()
        self.assertEqual(data['cpu_p_core_usage'],30);self.assertEqual(data['cpu_e_core_usage'],50)
        self.assertEqual(data['cpu_max_core_usage'],100)
    def test_missing_bad_or_overlapping_topology_never_infers_hybrid(self):
        self.topology();self.write('bus/event_source/devices/cpu_core/cpus','0-x')
        data=self.sensor.snapshot();self.assertIsNone(data['cpu_p_core_mhz']);self.assertEqual(data['cpu_e_core_mhz'],2000)
        self.write('bus/event_source/devices/cpu_core/cpus','0-3')
        data=self.sensor.snapshot();self.assertIsNone(data['cpu_p_core_mhz']);self.assertIsNone(data['cpu_e_core_mhz'])
        for text in ('3-1','0,','-1','0-999999999','0x3','1 2'):
            self.assertIsNone(self.sensor.parse_cpu_list(text))
        self.assertEqual(self.sensor.parse_cpu_list('0-2,4,2'),{0,1,2,4})
    def test_hotplug_and_reset_cpu_rebaseline_individually(self):
        self.topology();self.stat({0:(10,90,0),1:(10,90,0)});self.sensor.core_usage()
        self.now=1;self.stat({0:(20,180,0),1:(5,5,0),2:(30,70,0)})
        self.assertEqual(self.sensor.core_usage(),{0:10})
        self.now=2;self.stat({0:(30,270,0),1:(25,85,0),2:(60,140,0)})
        self.assertEqual(self.sensor.core_usage(),{0:10,1:20,2:30})
        self.write('devices/system/cpu/online','0-1');self.now=3
        self.assertNotIn(2,self.sensor.core_usage());self.assertNotIn(2,self.sensor.frequencies())
        self.write('devices/system/cpu/online','0-3');self.now=4;self.stat({0:(40,360,0),2:(90,210,0)})
        self.assertNotIn(2,self.sensor.core_usage())
    def test_missing_stat_bad_sample_long_interval_and_clock_reset(self):
        self.topology();self.stat({0:(10,90,0)});self.sensor.core_usage()
        self.now=1;(self.procroot/'stat').write_text('cpu0 bad 0 0 1\ncpu1 -1 0 0 1\n')
        self.assertEqual(self.sensor.core_usage(),{})
        self.now=2;self.stat({0:(20,180,0)});self.assertEqual(self.sensor.core_usage(),{})
        self.now=20;self.stat({0:(30,270,0)});self.assertEqual(self.sensor.core_usage(),{})
        self.now=19;self.assertEqual(self.sensor.core_usage(),{})
        self.now=20;self.stat({0:(40,360,0)});self.assertEqual(self.sensor.core_usage(),{0:10})
        (self.procroot/'stat').unlink();self.now=21;self.assertEqual(self.sensor.core_usage(),{})
    def test_offline_files_invalid_online_and_missing_group_frequency(self):
        self.topology();self.write('devices/system/cpu/cpu0/online','0')
        self.assertEqual(self.sensor.snapshot()['cpu_p_core_mhz'],4000)
        self.write('devices/system/cpu/online','invalid')
        self.assertEqual(self.sensor.frequencies(),{})
        self.write('devices/system/cpu/online','0-1')
        self.assertIsNone(self.sensor.snapshot()['cpu_e_core_mhz'])
    def test_memory_used_uses_available_not_free_and_checks_bounds(self):
        (self.procroot/'meminfo').write_text('MemTotal: 8388608 kB\nMemFree: 1 kB\nMemAvailable: 2097152 kB\n')
        self.assertEqual(self.sensor.memory_used_gb(),6)
        for text in ('MemTotal: 4 kB\nMemAvailable: 5 kB\n','MemTotal: 4 kB\n','MemTotal: nope kB\nMemAvailable: 1 kB\n'):
            (self.procroot/'meminfo').write_text(text);self.assertIsNone(self.sensor.memory_used_gb())
if __name__=='__main__':unittest.main()
