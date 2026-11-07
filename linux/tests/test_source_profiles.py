"""Synthetic sysfs and pure decisions; no live profile writes."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_profiles import SourceProfiles,SOURCE_PROFILE_NAMES,detect_source,UNKNOWN

class DetectionTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def supply(self,name,**fields):
        path=self.root/'class/power_supply'/name;path.mkdir(parents=True,exist_ok=True)
        for key,value in fields.items():(path/key).write_text(value)
    def test_missing_empty_and_unknown_never_infer_battery(self):
        self.assertEqual(detect_source(self.root),UNKNOWN)
        self.supply('BAT',type='Battery',status='Not charging',capacity='80')
        self.assertEqual(detect_source(self.root),UNKNOWN)
    def test_mains_precedes_online_usb_independent_of_enumeration(self):
        self.supply('usb',type='USB',online='1',usb_type='[C] PD PD_PPS')
        self.assertEqual(detect_source(self.root),'USB-C')
        self.supply('ac',type='Mains',online='1');self.assertEqual(detect_source(self.root),'AC')
    def test_usb_family_including_pd_and_type_c(self):
        for kind in ('USB','USB_C','USB_PD','USB_PD_DRP','USB_DCP','USB Type-C'):
            self.supply('usb',type=kind,online='1');self.assertEqual(detect_source(self.root),'USB-C')
        self.supply('usb',online='0');self.assertEqual(detect_source(self.root),UNKNOWN)
    def test_battery_requires_discharging_not_absent_and_no_external_unknown(self):
        self.supply('bat',type='Battery',status='Discharging',present='1')
        self.supply('ac',type='Mains',online='0');self.assertEqual(detect_source(self.root),'Battery')
        self.supply('usb',type='USB');self.assertEqual(detect_source(self.root),UNKNOWN)
        self.supply('usb',online='0');self.assertEqual(detect_source(self.root),'Battery')
        self.supply('bat',present='0');self.assertEqual(detect_source(self.root),UNKNOWN)
    def test_unknown_online_and_contradictory_batteries_remain_unknown(self):
        self.supply('bat',type='Battery',status='Discharging')
        self.supply('other',type='Wireless',online='1');self.assertEqual(detect_source(self.root),UNKNOWN)
        self.supply('other',online='0');self.supply('bat2',type='Battery',status='Charging')
        self.assertEqual(detect_source(self.root),UNKNOWN)
    def test_invalid_online_not_treated_as_offline(self):
        self.supply('bat',type='Battery',status='Discharging')
        for online in ('bad','','2','-1'):
            self.supply('ac',type='Mains',online=online);self.assertEqual(detect_source(self.root),UNKNOWN)

class ControllerTests(unittest.TestCase):
    def setUp(self):self.controller=SourceProfiles({'AC':'Performance','USB-C':'Balanced','Battery':'Eco'})
    def test_original_profile_order_and_disabled_defaults(self):
        self.assertEqual(SOURCE_PROFILE_NAMES,('Eco','Quiet','Balanced','Performance','Turbo'))
        controller=SourceProfiles();self.assertFalse(controller.enabled)
        for source in ('AC','Battery','USB-C'):self.assertIsNone(controller.poll(source,'Quiet'))
    def test_once_per_transition_and_same_mode_consumes_decision(self):
        self.assertEqual(self.controller.poll('AC','Balanced'),'Performance')
        self.assertIsNone(self.controller.poll('AC','Balanced'))
        self.assertIsNone(self.controller.poll('Battery','Eco'))
        self.assertIsNone(self.controller.poll('Battery','Quiet'))
        self.assertEqual(self.controller.poll('USB-C','Quiet'),'Balanced')
    def test_unknown_does_not_create_transition_or_release_manual_choice(self):
        self.controller.poll('AC','Balanced');self.controller.manual_override('Turbo')
        for source in ('AC',UNKNOWN,'AC',UNKNOWN):self.assertIsNone(self.controller.poll(source,'Turbo'))
        self.assertEqual(self.controller.poll('Battery','Turbo'),'Eco')
    def test_manual_override_before_initial_detection_is_preserved(self):
        self.controller.manual_override('Turbo');self.assertIsNone(self.controller.poll('AC','Turbo'))
        self.assertEqual(self.controller.poll('Battery','Turbo'),'Eco')
    def test_runtime_configuration_applies_once_without_repeated_identical_config(self):
        self.controller.poll('AC','Performance');mapping={'AC':'Quiet'}
        self.controller.configure(mapping);mapping['AC']='Turbo'
        self.assertEqual(self.controller.poll('AC','Performance'),'Quiet')
        self.controller.configure({'AC':'Quiet'});self.assertIsNone(self.controller.poll('AC','Performance'))
        self.controller.configure({});self.assertFalse(self.controller.enabled)
        self.controller.configure({'AC':'Eco'});self.assertEqual(self.controller.poll('AC','Quiet'),'Eco')
    def test_configuration_does_not_discard_manual_hold_or_write_unknown_source(self):
        self.controller.poll('AC','Performance');self.controller.manual_override('Turbo')
        self.controller.configure({'AC':'Quiet','Battery':'Eco'})
        self.assertIsNone(self.controller.poll('AC','Turbo'))
        self.assertEqual(self.controller.poll('Battery','Turbo'),'Eco')
        self.controller.configure({'AC':'Quiet'});self.assertIsNone(self.controller.poll(UNKNOWN,'Eco'))
        self.assertIsNone(self.controller.poll('Battery','Eco'))
    def test_validation_atomic_and_partial_mapping_has_no_fallback(self):
        for mapping in (None,[],{'AC':'Invalid'},{'Unknown':'Eco'},{'AC':'Quiet','Battery':'eco'}):
            with self.assertRaises(ValueError):self.controller.configure(mapping)
        self.assertEqual(self.controller.mapping['AC'],'Performance')
        for mode in ('invalid',None,1):
            with self.assertRaises(ValueError):self.controller.manual_override(mode)
        with self.assertRaises(ValueError):self.controller.poll('usb','Balanced')
        self.controller.configure({'AC':'Quiet'});self.assertIsNone(self.controller.poll('Battery','Performance'))
if __name__=='__main__':unittest.main()
