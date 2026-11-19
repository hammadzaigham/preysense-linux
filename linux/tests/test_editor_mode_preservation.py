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
  window.apply.assert_not_called()
  window.submit_tuning_request.assert_called_once_with(
   {'mode':'5','cpu':{'pl1':65,'pl2':100,'tau':56},'gpu':None,'prochot':None,'save':False,'reset':False})

 def test_tuning_status_reports_worker_result(self):
  window = Mock()
  request = {'mode':'1','cpu':{'boost':False},'gpu':None,'prochot':None,'save':False,'reset':False}
  window._tuning_pending = None
  Window.submit_tuning_request(window, request)
  window.set_tuning_status.assert_called_once_with('')
  window.command.emit.assert_called_once_with('tuning_apply', request)
  Window.finish_tuning_request(window, 'tuning_applied', '')
  window.set_tuning_status.assert_called_with('Applied and read back successfully.')
  self.assertIsNone(window._tuning_pending)

 def test_failed_tuning_request_does_not_report_success_or_save(self):
  window = Mock()
  window._tuning_pending = {'mode':'1','cpu':{'boost':False},'gpu':None,'prochot':None,'save':True,'reset':False}
  Window.finish_tuning_request(window, 'tuning_apply', 'CPU boost readback failed')
  window.set_tuning_status.assert_called_once_with('Could not apply: CPU boost readback failed', is_error=True)
  window.settings.setValue.assert_not_called()
