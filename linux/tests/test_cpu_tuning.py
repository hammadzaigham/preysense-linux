import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cpu_tuning import observed_policy
class CpuTuningTests(unittest.TestCase):
 def test_mode_defaults_use_effective_domains_not_startup_ceiling(self):
  for pl1,pl2 in ((45,50),(65,140),(75,140),(85,140)):
   cpu={'ceilings':[65,140],'domains':{'msr':{'pl1':115,'pl2':140,'tau':55.967744},'mmio':{'pl1':pl1,'pl2':pl2,'tau':55.967744}}}
   self.assertEqual(observed_policy(cpu),{'pl1':pl1,'pl2':pl2,'tau':56})
 def test_unavailable_data_stays_unavailable(self):
  self.assertIsNone(observed_policy({}))
  self.assertIsNone(observed_policy({'domains':{'x':{'pl1':float('nan'),'pl2':140,'tau':56}}}))
