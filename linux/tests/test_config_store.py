import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config_store import ConfigStore, JsonSettings, default_config


class FakeSettings:
    def __init__(self, values): self._values=dict(values)
    def contains(self,key): return key in self._values
    def value(self,key,default=None): return self._values.get(key,default)


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'preysense.json'
    def tearDown(self): self.temp.cleanup()
    def test_defaults_and_round_trip(self):
        store=ConfigStore(self.path)
        self.assertEqual(store.data['SchemaVersion'],2)
        store.data['General']['Language']='zh-CN'
        store.save()
        again=ConfigStore(self.path)
        self.assertEqual(again.data['General']['Language'],'zh-CN')
    def test_migrate_qsettings_fans_and_theme(self):
        store=ConfigStore(self.path)
        settings=FakeSettings({
            'theme':'Light','language':'en-US',
            'fan_policies':json.dumps({'1':{'kind':'Max'}}),
            'power_policies':json.dumps({'5':{'pl1':90,'pl2':115,'tau':56,'boost':True}}),
        })
        store.migrate_from_qsettings(settings)
        self.assertTrue(store.data['General']['LightTheme'])
        self.assertEqual(store.data['Fans']['Balanced']['ControlMode'],1)
        self.assertEqual(store.data['Tuning']['Turbo']['CpuPl1Watts'],90)
        facade=JsonSettings(store)
        self.assertEqual(facade.value('theme'),'Light')
        fans=json.loads(facade.value('fan_policies'))
        self.assertEqual(fans['1']['kind'],'Max')
    def test_migrate_calibration_json(self):
        cal=Path(self.temp.name)/'calibration.json'
        cal.write_text(json.dumps({'Balanced':{'pl1':65,'pl2':140,'tau':56}}))
        store=ConfigStore(self.path)
        self.assertTrue(store.migrate_calibration_json(cal))
        self.assertEqual(store.data['Tuning']['FactoryDefaults']['Balanced']['CpuPl1Watts'],65)

    def test_tuning_persistence_keys(self):
        store=ConfigStore(self.path)
        facade=JsonSettings(store)
        facade.setValue('tuning_enabled', True)
        facade.setValue('apply_prochot', True)
        facade.setValue('prochot_offset', 11)
        facade.setValue('factory_prochot_offset', 7)
        facade.setValue('factory_tjmax', 100)
        facade.setValue('power_policies', json.dumps({'4':{'pl1':80,'pl2':100,'tau':56,'boost':False}}))
        facade.setValue('gpu_policies', json.dumps({'4':{'ct':25,'db':15,'cp':20}}))
        again=JsonSettings(ConfigStore(self.path))
        self.assertTrue(again.value('tuning_enabled', type=bool))
        self.assertTrue(again.value('apply_prochot', type=bool))
        self.assertEqual(again.value('prochot_offset'), 11)
        self.assertEqual(again.value('factory_tjmax'), 100)
        power=json.loads(again.value('power_policies'))
        self.assertEqual(power['4']['pl1'], 80)
        self.assertTrue(ConfigStore(self.path).data['Tuning']['Performance']['ApplyCpuLimits'])
        gpu=json.loads(again.value('gpu_policies'))
        self.assertEqual(gpu['4']['ct'], 25)
        self.assertTrue(ConfigStore(self.path).data['Tuning']['Performance']['ApplyGpuLimits'])
        # Full replace clears modes omitted from the dump.
        facade.setValue('power_policies', json.dumps({}))
        self.assertFalse(ConfigStore(self.path).data['Tuning']['Performance']['ApplyCpuLimits'])


if __name__=='__main__':unittest.main()
