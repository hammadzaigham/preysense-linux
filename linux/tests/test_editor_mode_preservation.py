import sys,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preysense import Window
class EditorModeTests(unittest.TestCase):
 def test_turbo_max_saved_without_switching_balanced(self):
  window=Mock();window._confirmed_profile=1;window.fan_profile.currentData.return_value=5;window.fan_editor_policy.return_value={'kind':'Max'};window.saved_fan_policies={}
  Window.apply_fan_policy(window,True)
  window.apply.assert_called_once_with('fan_policy',{'mode':'5','policy':{'kind':'Max'}})
  self.assertEqual(window.saved_fan_policies['5'],{'kind':'Max'})
 def test_inactive_fan_apply_does_not_activate_mode(self):
  window=Mock();window._confirmed_profile=1;window.fan_profile.currentData.return_value=5;window.fan_editor_policy.return_value={'kind':'Max'}
  Window.apply_fan_policy(window,False)
  window.apply.assert_called_once_with('fan_policy',{'mode':'5','policy':{'kind':'Max'}})
 def test_power_apply_does_not_activate_mode(self):
  window=Mock();window._confirmed_profile=1;window.power_profile.currentData.return_value=5;window.power_pl1.value.return_value=65;window.power_pl2.value.return_value=100;window.power_tau.currentData.return_value=56
  Window.apply_power_policy(window,False)
  window.apply.assert_called_once_with('power_policy',{'mode':'5','policy':{'pl1':65,'pl2':100,'tau':56}})
