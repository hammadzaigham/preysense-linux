import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from power_ownership import PowerOwnership
class Power:
 def __init__(self):self.values={'domain':dict(pl1=65,pl2=140,tau=56)}
 def capture(self):return copy.deepcopy(self.values)
 def apply(self,**values):self.values['domain'].update(values)
 def restore(self,values):self.values.update(copy.deepcopy(values))
class OwnershipTests(unittest.TestCase):
 def test_multiple_edits_restore_original(self):
  p=Power();o=PowerOwnership(p);o.apply(pl1=55);o.apply(pl1=50);o.release();self.assertEqual(p.values['domain']['pl1'],65)
 def test_external_change_preserved_field_by_field(self):
  p=Power();o=PowerOwnership(p);o.apply(pl1=55,pl2=100);p.values['domain']['pl1']=60
  self.assertEqual(o.release(),['domain pl1']);self.assertEqual(p.values['domain'],dict(pl1=60,pl2=140,tau=56))
 def test_new_edit_after_external_change_uses_new_baseline(self):
  p=Power();o=PowerOwnership(p);o.apply(pl1=55);p.values['domain']['pl1']=60;o.apply(pl1=50);o.release();self.assertEqual(p.values['domain']['pl1'],60)
if __name__=='__main__':unittest.main()
