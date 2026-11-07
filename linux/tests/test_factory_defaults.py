import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from factory_defaults import ObservedDefaults, validate_domains

IDENTITY = dict(vendor='Acer', product='Predator PHN16S-71', bios='V1.28')
BASE = {'intel-rapl:0': dict(pl1=115.0, pl2=140.0, tau=55.967744),
        'intel-rapl-mmio:0': dict(pl1=65.0, pl2=140.0, tau=55.967744)}


class FakePower:
    def __init__(self):
        self.values = copy.deepcopy(BASE)
        self.enabled = True
        self.writes = []
    def capture(self): return copy.deepcopy(self.values)
    def boost(self): return self.enabled
    def restore(self, values):
        self.writes.append(('restore', copy.deepcopy(values)))
        self.values = copy.deepcopy(values)
    def set_boost(self, value):
        self.writes.append(('boost', value)); self.enabled = value


class ObservedDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ObservedDefaults(Path(self.temp.name) / 'defaults', IDENTITY)
        self.power = FakePower()
        self.mode = 1
    def current(self): return self.mode
    def capture(self): return self.store.capture(1, self.power, self.current)

    def test_capture_is_read_only_immutable_and_explicitly_not_factory(self):
        saved = self.capture()
        self.assertEqual(self.power.writes, [])
        self.assertFalse(saved['factory_verified'])
        self.assertEqual(saved['domains'], BASE)
        path = self.store.directory / 'mode-1.json'
        original = path.read_bytes()
        self.assertEqual(path.stat().st_mode & 0o777, 0o400)
        self.power.values['intel-rapl:0']['pl1'] = 60
        with self.assertRaises(FileExistsError): self.capture()
        self.assertEqual(path.read_bytes(), original)

    def test_unstable_limits_and_mode_do_not_create_capture(self):
        changed = copy.deepcopy(BASE); changed['intel-rapl:0']['pl1'] = 60
        with patch.object(self.power, 'capture', side_effect=[BASE, changed]):
            with self.assertRaisesRegex(RuntimeError, 'changed during capture'): self.capture()
        self.assertFalse((self.store.directory / 'mode-1.json').exists())
        with self.assertRaisesRegex(RuntimeError, 'Select the requested mode'):
            self.store.capture(0, self.power, self.current)
        self.assertEqual(self.power.writes, [])

    def test_active_custom_policy_blocks_capture_and_reset(self):
        with self.assertRaisesRegex(RuntimeError, 'Stop custom CPU'):
            self.store.capture(1, self.power, self.current, controller_active=True)
        self.capture()
        with self.assertRaisesRegex(RuntimeError, 'Stop custom CPU'):
            self.store.reset(1, self.power, self.current, controller_active=True)
        self.assertEqual(self.power.writes, [])

    def test_identity_bios_and_corruption_block_reset_before_writes(self):
        self.capture()
        other = ObservedDefaults(self.store.directory, dict(IDENTITY, bios='V1.29'))
        with self.assertRaisesRegex(ValueError, 'another machine, BIOS or mode'):
            other.reset(1, self.power, self.current)
        path = self.store.directory / 'mode-1.json'
        path.chmod(0o600)
        value = json.loads(path.read_text()); value['snapshot']['domains']['intel-rapl:0']['pl1'] = 99
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.store.reset(1, self.power, self.current)
        self.assertEqual(self.power.writes, [])

    def test_reset_restores_different_msr_mmio_and_boost(self):
        self.capture()
        for values in self.power.values.values(): values.update(pl1=55, pl2=100, tau=16)
        self.power.enabled = False
        result = self.store.reset(1, self.power, self.current)
        self.assertEqual(self.power.values, BASE)
        self.assertTrue(self.power.enabled)
        self.assertFalse(result['factory_verified'])

    def test_reset_rejects_wrong_mode_or_missing_domain(self):
        self.capture(); self.mode = 0
        with self.assertRaisesRegex(RuntimeError, 'currently active mode'):
            self.store.reset(1, self.power, self.current)
        self.mode = 1; self.power.values.pop('intel-rapl:0')
        with self.assertRaisesRegex(RuntimeError, 'domain layout changed'):
            self.store.reset(1, self.power, self.current)
        self.assertEqual(self.power.writes, [])

    def test_partial_reset_failure_rolls_back_original_live_values(self):
        self.capture()
        self.power.values['intel-rapl:0']['pl1'] = 55
        before = self.power.capture(); original = self.power.restore
        calls = []
        def partial(values):
            calls.append(values)
            if len(calls) == 1:
                self.power.values = copy.deepcopy(values)
                raise OSError('domain write rejected')
            original(values)
        with patch.object(self.power, 'restore', side_effect=partial):
            with self.assertRaisesRegex(OSError, 'rejected'):
                self.store.reset(1, self.power, self.current)
        self.assertEqual(self.power.values, before)

    def test_failed_readback_rolls_back_and_does_not_rewrite_capture(self):
        self.capture(); original_file = (self.store.directory / 'mode-1.json').read_bytes()
        self.power.values['intel-rapl:0']['pl1'] = 55
        before = self.power.capture()
        original = self.power.restore
        count = [0]
        def ignored_once(values):
            count[0] += 1
            if count[0] > 1: original(values)
        with patch.object(self.power, 'restore', side_effect=ignored_once):
            with self.assertRaisesRegex(RuntimeError, 'readback failed'):
                self.store.reset(1, self.power, self.current)
        self.assertEqual(self.power.values, before)
        self.assertEqual((self.store.directory / 'mode-1.json').read_bytes(), original_file)

    def test_mode_changed_during_reset_does_not_overwrite_new_firmware_policy(self):
        self.capture()
        def firmware_changed(values):
            self.mode = 0
            self.power.values['intel-rapl:0']['pl1'] = 45
        with patch.object(self.power, 'restore', side_effect=firmware_changed) as restore:
            with self.assertRaisesRegex(RuntimeError, 'rollback was skipped'):
                self.store.reset(1, self.power, self.current)
            self.assertEqual(restore.call_count, 1)
        self.assertEqual(self.power.values['intel-rapl:0']['pl1'], 45)

    def test_invalid_domains_values_and_boost_are_not_captured(self):
        for bad in ({}, {'../unsafe': dict(pl1=50, pl2=100, tau=16)},
                    {'intel-rapl:0': dict(pl1=float('nan'), pl2=100, tau=16)},
                    {'intel-rapl:0': dict(pl1=True, pl2=100, tau=16)},
                    {'intel-rapl:0': dict(pl1=60, pl2=50, tau=16)}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate_domains(bad)
        with patch.object(self.power, 'boost', return_value='yes'):
            with self.assertRaisesRegex(ValueError, 'boost'): self.capture()

    def test_capture_atomic_link_race_never_overwrites_completed_file(self):
        self.store.directory.mkdir()
        target = self.store.directory / 'mode-1.json'
        def race(source, destination):
            target.write_text('other capture won')
            raise FileExistsError('already captured')
        with patch('factory_defaults.os.link', side_effect=race):
            with self.assertRaises(FileExistsError): self.capture()
        self.assertEqual(target.read_text(), 'other capture won')
        self.assertEqual(list(self.store.directory.glob('.capture-*')), [])

    def test_status_reports_partial_capture_and_integrity_errors(self):
        self.capture(); status = self.store.status()
        self.assertTrue(status['1']['available'])
        self.assertFalse(status['0']['available'])
        self.assertEqual(status['0']['error'], 'Not captured')
        self.assertFalse(status['1']['factory_verified'])

    def test_symlink_snapshot_is_rejected(self):
        self.store.directory.mkdir()
        target = Path(self.temp.name) / 'target'; target.write_text('{}')
        (self.store.directory / 'mode-1.json').symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'symlink'): self.store.load(1)
        with self.assertRaises(FileExistsError): self.capture()


if __name__ == '__main__': unittest.main()
