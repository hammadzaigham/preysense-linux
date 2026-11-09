"""Unified preysense.json store aligned with the Windows SchemaVersion 2 layout."""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

SCHEMA_VERSION = 2
MODE_NAMES = ('Quiet', 'Eco', 'Balanced', 'Performance', 'Turbo')
MODE_CODES = {'Quiet': 0, 'Eco': 6, 'Balanced': 1, 'Performance': 4, 'Turbo': 5}
CODE_TO_NAME = {str(v): k for k, v in MODE_CODES.items()}


def default_config_path():
    override = os.environ.get('PREYSENSE_CONFIG')
    if override:
        return Path(override)
    base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'PreySense' / 'preysense.json'


def _mode_tuning():
    return {
        'ApplyCpuLimits': False,
        'CpuPl1Watts': None,
        'CpuPl2Watts': None,
        'CpuTurboTimeLimitSeconds': None,
        'CpuBoostMode': None,
        'CpuBoost': None,
        'ApplyGpuLimits': False,
        'GpuPowerOffsetWatts': None,
        'GpuDynamicBoostWatts': None,
        'PlatformPowerOffsetWatts': None,
        'GpuNominalPowerWatts': None,
    }


def _mode_fans():
    return {'ControlMode': 0, 'RampUpSeconds': 2, 'Stages': None}


def default_config():
    tuning = {
        'ApplyProchotOffset': False,
        'ProchotOffsetCelsius': None,
        'FactoryProchotOffsetCelsius': None,
        'FactoryProchotOffsetLocked': None,
        'FactoryTjMaxCelsius': None,
        'GpuBasePowerWatts': None,
        'FactoryStaticCpuPl1Watts': None,
        'FactoryStaticCpuPl2Watts': None,
        'FactoryDefaults': {},
    }
    fans = {}
    for name in MODE_NAMES:
        tuning[name] = _mode_tuning()
        fans[name] = _mode_fans()
    return {
        'SchemaVersion': SCHEMA_VERSION,
        'General': {
            'Language': 'en-US',
            'LightTheme': False,
            'HardwareTuningEnabled': False,
        },
        'Display': {'AutoRefreshRate': False},
        'Battery': {
            'ChargeLimitEnabled': True,
            'UsbPowerOffChargingCutoffPercent': 0,
        },
        'Session': {
            'ActivePowerMode': 1,
            'AcPowerMode': 1,
            'BatteryPowerMode': 6,
            'GpuModePreference': 1,
        },
        'Tuning': tuning,
        'Fans': fans,
        'Lighting': {
            'Keyboard': {
                'Brightness': 100,
                'Speed': 5,
                'BacklightTimeoutSeconds': 30,
                'SelectedColorHex': '#28d8ca',
                'SyncZones': True,
                'Zone1ColorHex': '#28d8ca',
                'Zone2ColorHex': '#28d8ca',
                'Zone3ColorHex': '#28d8ca',
                'Zone4ColorHex': '#28d8ca',
                'EffectTag': 'Static',
                'PresetTheme': 'Custom',
            },
            'Cover': {
                'Enabled': True,
                'ColorHex': '#28d8ca',
                'Brightness': 80,
                'Speed': 5,
                'SyncWithKeyboard': False,
                'EffectTag': 'Static',
            },
        },
        'Overlay': {
            'Enabled': False,
            'ScalePercent': 100,
            'BackgroundOpacityPercent': 50,
            'TextOpacityPercent': 100,
            'PositionHorizontal': 'Left',
            'PositionVertical': 'Top',
            'CornerRadiusPixels': 6,
            'Slots': [
                {'CpuMetric': 'Usage', 'GpuMetric': 'Usage', 'ShowGraph': False},
                {'CpuMetric': 'Temperature', 'GpuMetric': 'Temperature', 'ShowGraph': False},
                {'CpuMetric': 'Effective Clock', 'GpuMetric': 'Clock', 'ShowGraph': False},
                {'CpuMetric': 'Power', 'GpuMetric': 'Power', 'ShowGraph': True},
                {'CpuMetric': 'Memory', 'GpuMetric': 'Memory', 'ShowGraph': False},
                {'CpuMetric': 'Memory Speed', 'GpuMetric': 'Memory Speed', 'ShowGraph': False},
            ],
        },
    }


def _deep_merge(base, overlay):
    if not isinstance(overlay, dict):
        return deepcopy(base)
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_config_path()
        self.data = default_config()
        self._dirty = False
        self.load()

    def load(self):
        try:
            if self.path.is_symlink():
                raise ValueError('Configuration symlink is not accepted')
            text = self.path.read_text(encoding='utf-8')
            loaded = json.loads(text)
            if not isinstance(loaded, dict):
                raise ValueError('Configuration root must be an object')
            version = loaded.get('SchemaVersion')
            if version != SCHEMA_VERSION:
                raise ValueError(f'SchemaVersion {SCHEMA_VERSION} required')
            self.data = _deep_merge(default_config(), loaded)
            self.data['SchemaVersion'] = SCHEMA_VERSION
        except FileNotFoundError:
            self.data = default_config()
        except (OSError, ValueError, json.JSONDecodeError):
            # Keep defaults in memory; do not destroy a bad file automatically.
            self.data = default_config()
        self._dirty = False
        return self.data

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(self.data, indent=2, ensure_ascii=False) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.preysense-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            temporary = None
            self._dirty = False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def update(self, mutator):
        mutator(self.data)
        self._dirty = True
        self.save()

    def migrate_from_qsettings(self, settings):
        """One-shot import of flat QSettings keys into nested JSON."""
        def val(key, default=None):
            try:
                return settings.value(key, default)
            except Exception:
                return default

        def has(key):
            try:
                return settings.contains(key)
            except Exception:
                return False

        g = self.data['General']
        if has('theme'):
            g['LightTheme'] = str(val('theme', 'Dark')).lower() == 'light'
        if has('language'):
            g['Language'] = str(val('language', 'en-US'))
        d = self.data['Display']
        if has('auto_refresh'):
            d['AutoRefreshRate'] = bool(val('auto_refresh', False))
        b = self.data['Battery']
        if has('battery_limit'):
            try:
                b['ChargeLimitEnabled'] = int(val('battery_limit', 80)) <= 80
            except (TypeError, ValueError):
                pass
        if has('usb_charging'):
            try:
                b['UsbPowerOffChargingCutoffPercent'] = int(val('usb_charging', 0))
            except (TypeError, ValueError):
                pass
        s = self.data['Session']
        try:
            mapping = json.loads(val('source_profiles', '{}') or '{}')
            if isinstance(mapping, dict):
                ac = mapping.get('AC') or val('profile_ac', 'Balanced')
                bat = mapping.get('Battery') or val('profile_battery', 'Eco')
                s['AcPowerMode'] = MODE_CODES.get(str(ac), 1)
                s['BatteryPowerMode'] = MODE_CODES.get(str(bat), 6)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        # Fans / power policies keyed by mode code strings.
        try:
            fans = json.loads(val('fan_policies', '{}') or '{}')
            if isinstance(fans, dict):
                for code, policy in fans.items():
                    name = CODE_TO_NAME.get(str(code))
                    if not name or not isinstance(policy, dict):
                        continue
                    kind = policy.get('kind')
                    if kind not in ('Auto', 'Max', 'Custom'):
                        continue
                    slot = self.data['Fans'][name]
                    slot['ControlMode'] = {'Auto': 0, 'Max': 1, 'Custom': 2}[kind]
                    if kind == 'Custom':
                        slot['RampUpSeconds'] = int(policy.get('delay', 2) or 2)
                        if policy.get('stages'):
                            slot['Stages'] = policy['stages']
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        try:
            power = json.loads(val('power_policies', '{}') or '{}')

            if isinstance(power, dict):
                for code, policy in power.items():
                    name = CODE_TO_NAME.get(str(code))
                    if not name or not isinstance(policy, dict):
                        continue
                    slot = self.data['Tuning'][name]
                    slot['ApplyCpuLimits'] = True
                    slot['CpuPl1Watts'] = policy.get('pl1')
                    slot['CpuPl2Watts'] = policy.get('pl2')
                    slot['CpuTurboTimeLimitSeconds'] = policy.get('tau')
                    if 'boost' in policy:
                        slot['CpuBoost'] = bool(policy['boost'])
                        slot['CpuBoostMode'] = 1 if policy['boost'] else 0
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        lit = self.data['Lighting']['Keyboard']
        cover = self.data['Lighting']['Cover']
        if has('brightness'):
            lit['Brightness'] = int(val('brightness', 100))
        if has('speed'):
            lit['Speed'] = int(val('speed', 5))
        if has('effect'):
            lit['EffectTag'] = str(val('effect', 'Static'))
        if has('led_timeout'):
            lit['BacklightTimeoutSeconds'] = int(val('led_timeout', 30))
        if has('colors'):
            colors = val('colors', [])
            if isinstance(colors, list) and len(colors) >= 4:
                for i, key in enumerate(('Zone1ColorHex', 'Zone2ColorHex', 'Zone3ColorHex', 'Zone4ColorHex')):
                    lit[key] = str(colors[i])
                lit['SelectedColorHex'] = str(colors[0])
        if has('sync_logo'):
            cover['SyncWithKeyboard'] = bool(val('sync_logo', False))
        if has('logo_color'):
            cover['ColorHex'] = str(val('logo_color', '#28d8ca'))
        if has('logo_brightness'):
            cover['Brightness'] = int(val('logo_brightness', 80))
        if has('logo_effect'):
            cover['EffectTag'] = str(val('logo_effect', 'Static'))
        if has('logo_speed'):
            cover['Speed'] = int(val('logo_speed', 5))
        ov = self.data['Overlay']
        if has('overlay_visible'):
            ov['Enabled'] = bool(val('overlay_visible', False))
        if has('hud_scale'):
            ov['ScalePercent'] = int(val('hud_scale', 100))
        if has('hud_background'):
            ov['BackgroundOpacityPercent'] = int(val('hud_background', 50))
        if has('hud_text'):
            ov['TextOpacityPercent'] = int(val('hud_text', 100))
        if has('hud_h_pos'):
            ov['PositionHorizontal'] = str(val('hud_h_pos', 'Left'))
        if has('hud_v_pos'):
            ov['PositionVertical'] = str(val('hud_v_pos', 'Top'))
        if has('hud_corner_radius'):
            ov['CornerRadiusPixels'] = int(val('hud_corner_radius', 6))
        elif has('overlay_corner_radius'):
            ov['CornerRadiusPixels'] = int(val('overlay_corner_radius', 6))
        slot_count = int(val('overlay_slot_count', len(ov.get('Slots') or []))) if has('overlay_slot_count') else len(ov.get('Slots') or [])
        slots = []
        for i in range(max(slot_count, len(ov.get('Slots') or []))):
            key = f'overlay_col_{i + 1}'
            gkey = f'overlay_col_{i + 1}_graph'
            base = ov['Slots'][i] if i < len(ov.get('Slots') or []) else {'CpuMetric': 'None', 'GpuMetric': 'None', 'ShowGraph': False}
            if has(key):
                parts = str(val(key, 'None|None')).split('|')
                base = dict(base)
                base['CpuMetric'] = parts[0] if parts else 'None'
                base['GpuMetric'] = parts[1] if len(parts) > 1 else 'None'
            if has(gkey):
                base = dict(base)
                base['ShowGraph'] = bool(val(gkey, False))
            if has(key) or has(gkey) or i < len(ov.get('Slots') or []):
                slots.append(base)
        if has('overlay_slot_count') or any(has(f'overlay_col_{i + 1}') for i in range(12)):
            ov['Slots'] = slots[: max(0, int(val('overlay_slot_count', len(slots))) if has('overlay_slot_count') else len(slots))]
        self.save()

    def migrate_calibration_json(self, path=None):
        base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        path = Path(path) if path else base / 'PreySense' / 'calibration.json'
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(raw, dict):
            return False
        factory = self.data['Tuning'].setdefault('FactoryDefaults', {})
        changed = False
        for name, values in raw.items():
            if name not in MODE_NAMES or not isinstance(values, dict):
                continue
            pl1 = values.get('CpuPl1Watts', values.get('pl1'))
            pl2 = values.get('CpuPl2Watts', values.get('pl2'))
            tau = values.get('CpuTurboTimeLimitSeconds', values.get('tau'))
            if pl1 is None or pl2 is None or tau is None:
                continue
            factory[name] = {
                'CpuPl1Watts': int(round(float(pl1))),
                'CpuPl2Watts': int(round(float(pl2))),
                'CpuTurboTimeLimitSeconds': int(round(float(tau))),
                'CpuBoost': values.get('CpuBoost', values.get('boost')),
                'CpuBoostMode': values.get('CpuBoostMode'),
                'ApplyCpuLimits': False,
                'ApplyGpuLimits': False,
            }
            changed = True
        if changed:
            self.save()
        return changed


class JsonSettings:
    """QSettings-compatible facade over ConfigStore for existing call sites."""

    def __init__(self, store=None):
        self.store = store or ConfigStore()
        self._migrated = False

    def ensure_migrated(self, qsettings=None):
        if self._migrated:
            return
        self._migrated = True
        if self.store.path.exists():
            return
        if qsettings is not None:
            self.store.migrate_from_qsettings(qsettings)
        self.store.migrate_calibration_json()

    def sync(self):
        if self.store._dirty:
            self.store.save()

    def contains(self, key):
        try:
            self.value(key, _MISSING)
            return True
        except KeyError:
            return False

    def value(self, key, default=None, type=None):
        data = self.store.data
        try:
            raw = self._get(key, data)
        except KeyError:
            raw = default
        if type is bool:
            if isinstance(raw, str):
                return raw.lower() in ('1', 'true', 'yes')
            return bool(raw)
        if type is int:
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default
        return raw

    def setValue(self, key, value):
        self._set(key, value, self.store.data)
        self.store._dirty = True
        self.store.save()

    def _get(self, key, data):
        g, d, b, s = data['General'], data['Display'], data['Battery'], data['Session']
        lit, cover, ov = data['Lighting']['Keyboard'], data['Lighting']['Cover'], data['Overlay']
        if key == 'theme':
            return 'Light' if g.get('LightTheme') else 'Dark'
        if key == 'language':
            return g.get('Language', 'en-US')
        if key == 'tuning_enabled':
            return bool(g.get('HardwareTuningEnabled'))
        if key == 'apply_prochot':
            return bool(data['Tuning'].get('ApplyProchotOffset'))
        if key == 'prochot_offset':
            return data['Tuning'].get('ProchotOffsetCelsius')
        if key == 'factory_prochot_offset':
            return data['Tuning'].get('FactoryProchotOffsetCelsius')
        if key == 'factory_prochot_locked':
            return data['Tuning'].get('FactoryProchotOffsetLocked')
        if key == 'factory_tjmax':
            return data['Tuning'].get('FactoryTjMaxCelsius')
        if key == 'gpu_base_watts':
            return data['Tuning'].get('GpuBasePowerWatts')
        if key == 'gpu_policies':
            return json.dumps(self._export_gpu_policies())
        if key == 'auto_refresh':
            return bool(d.get('AutoRefreshRate'))
        if key == 'battery_limit':
            return 80 if b.get('ChargeLimitEnabled', True) else 100
        if key == 'usb_charging':
            return int(b.get('UsbPowerOffChargingCutoffPercent', 0) or 0)
        if key == 'source_profiles':
            return json.dumps({
                'AC': CODE_TO_NAME.get(str(s.get('AcPowerMode', 1)), 'Balanced'),
                'Battery': CODE_TO_NAME.get(str(s.get('BatteryPowerMode', 6)), 'Eco'),
            })
        if key == 'profile_ac':
            return CODE_TO_NAME.get(str(s.get('AcPowerMode', 1)), 'Balanced')
        if key == 'profile_battery':
            return CODE_TO_NAME.get(str(s.get('BatteryPowerMode', 6)), 'Eco')
        if key == 'fan_policies':
            return json.dumps(self._export_fan_policies())
        if key == 'power_policies':
            return json.dumps(self._export_power_policies())
        if key == 'overlay_visible':
            return bool(ov.get('Enabled'))
        if key == 'overlay_slot_count':
            return len(ov.get('Slots') or [])
        if key == 'hud_scale':
            return int(ov.get('ScalePercent', 100))
        if key == 'hud_background':
            return int(ov.get('BackgroundOpacityPercent', 50))
        if key == 'hud_text':
            return int(ov.get('TextOpacityPercent', 100))
        if key == 'hud_h_pos':
            return ov.get('PositionHorizontal', 'Left')
        if key == 'hud_v_pos':
            return ov.get('PositionVertical', 'Top')
        if key in ('hud_corner_radius', 'overlay_corner_radius'):
            return int(ov.get('CornerRadiusPixels', 6))
        if key == 'hud_position':
            return f"{ov.get('PositionVertical', 'Top')} {ov.get('PositionHorizontal', 'Left').lower()}"
        if key == 'brightness':
            return int(lit.get('Brightness', 100))
        if key == 'speed':
            return int(lit.get('Speed', 5))
        if key == 'effect':
            return lit.get('EffectTag', 'Static')
        if key == 'led_timeout':
            return int(lit.get('BacklightTimeoutSeconds', 30))
        if key == 'colors':
            return [lit.get(f'Zone{i}ColorHex', '#28d8ca') for i in range(1, 5)]
        if key == 'sync_logo':
            return bool(cover.get('SyncWithKeyboard'))
        if key == 'logo_color':
            return cover.get('ColorHex', '#28d8ca')
        if key == 'logo_brightness':
            return int(cover.get('Brightness', 80))
        if key == 'logo_effect':
            return cover.get('EffectTag', 'Static')
        if key == 'logo_speed':
            return int(cover.get('Speed', 5))
        if key.startswith('overlay_col_') and key.endswith('_graph'):
            index = int(key[len('overlay_col_'):-len('_graph')]) - 1
            return bool(ov['Slots'][index].get('ShowGraph'))
        if key.startswith('overlay_col_'):
            index = int(key[len('overlay_col_'):]) - 1
            slot = ov['Slots'][index]
            return f"{slot.get('CpuMetric', 'None')}|{slot.get('GpuMetric', 'None')}"
        raise KeyError(key)

    def _set(self, key, value, data):
        g, d, b, s = data['General'], data['Display'], data['Battery'], data['Session']
        lit, cover, ov = data['Lighting']['Keyboard'], data['Lighting']['Cover'], data['Overlay']
        if key == 'theme':
            g['LightTheme'] = str(value).lower() == 'light'; return
        if key == 'language':
            g['Language'] = str(value); return
        if key == 'tuning_enabled':
            g['HardwareTuningEnabled'] = bool(value); return
        if key == 'apply_prochot':
            data['Tuning']['ApplyProchotOffset'] = bool(value); return
        if key == 'prochot_offset':
            data['Tuning']['ProchotOffsetCelsius'] = None if value in (None, '') else int(value); return
        if key == 'factory_prochot_offset':
            data['Tuning']['FactoryProchotOffsetCelsius'] = None if value in (None, '') else int(value); return
        if key == 'factory_prochot_locked':
            data['Tuning']['FactoryProchotOffsetLocked'] = None if value in (None, '') else bool(value); return
        if key == 'factory_tjmax':
            data['Tuning']['FactoryTjMaxCelsius'] = None if value in (None, '') else int(value); return
        if key == 'gpu_base_watts':
            data['Tuning']['GpuBasePowerWatts'] = None if value in (None, '') else int(value); return
        if key == 'gpu_policies':
            self._import_gpu_policies(json.loads(value) if isinstance(value, str) else value); return
        if key == 'auto_refresh':
            d['AutoRefreshRate'] = bool(value); return
        if key == 'battery_limit':
            b['ChargeLimitEnabled'] = int(value) <= 80; return
        if key == 'usb_charging':
            b['UsbPowerOffChargingCutoffPercent'] = int(value); return
        if key == 'source_profiles':
            mapping = json.loads(value) if isinstance(value, str) else value
            s['AcPowerMode'] = MODE_CODES.get(str(mapping.get('AC', 'Balanced')), 1)
            s['BatteryPowerMode'] = MODE_CODES.get(str(mapping.get('Battery', 'Eco')), 6)
            return
        if key == 'profile_ac':
            s['AcPowerMode'] = MODE_CODES.get(str(value), 1); return
        if key == 'profile_battery':
            s['BatteryPowerMode'] = MODE_CODES.get(str(value), 6); return
        if key == 'fan_policies':
            self._import_fan_policies(json.loads(value) if isinstance(value, str) else value); return
        if key == 'power_policies':
            self._import_power_policies(json.loads(value) if isinstance(value, str) else value); return
        if key == 'overlay_visible':
            ov['Enabled'] = bool(value); return
        if key == 'overlay_slot_count':
            count = max(0, min(12, int(value)))
            slots = list(ov.get('Slots') or [])
            while len(slots) < count:
                slots.append({'CpuMetric': 'None', 'GpuMetric': 'None', 'ShowGraph': False})
            ov['Slots'] = slots[:count]
            return
        if key == 'hud_scale':
            ov['ScalePercent'] = int(value); return
        if key == 'hud_background':
            ov['BackgroundOpacityPercent'] = int(value); return
        if key == 'hud_text':
            ov['TextOpacityPercent'] = int(value); return
        if key == 'hud_h_pos':
            ov['PositionHorizontal'] = str(value); return
        if key == 'hud_v_pos':
            ov['PositionVertical'] = str(value); return
        if key in ('hud_corner_radius', 'overlay_corner_radius'):
            ov['CornerRadiusPixels'] = int(value); return
        if key == 'brightness':
            lit['Brightness'] = int(value); return
        if key == 'speed':
            lit['Speed'] = int(value); return
        if key == 'effect':
            lit['EffectTag'] = str(value); return
        if key == 'led_timeout':
            lit['BacklightTimeoutSeconds'] = int(value); return
        if key == 'colors':
            colors = list(value)
            for i, name in enumerate(('Zone1ColorHex', 'Zone2ColorHex', 'Zone3ColorHex', 'Zone4ColorHex')):
                if i < len(colors):
                    lit[name] = str(colors[i])
            if colors:
                lit['SelectedColorHex'] = str(colors[0])
            return
        if key == 'sync_logo':
            cover['SyncWithKeyboard'] = bool(value); return
        if key == 'logo_color':
            cover['ColorHex'] = str(value); return
        if key == 'logo_brightness':
            cover['Brightness'] = int(value); return
        if key == 'logo_effect':
            cover['EffectTag'] = str(value); return
        if key == 'logo_speed':
            cover['Speed'] = int(value); return
        if key.startswith('overlay_col_') and key.endswith('_graph'):
            index = int(key[len('overlay_col_'):-len('_graph')]) - 1
            slots = ov.setdefault('Slots', [])
            while len(slots) <= index:
                slots.append({'CpuMetric': 'None', 'GpuMetric': 'None', 'ShowGraph': False})
            slots[index]['ShowGraph'] = bool(value); return
        if key.startswith('overlay_col_'):
            index = int(key[len('overlay_col_'):]) - 1
            slots = ov.setdefault('Slots', [])
            while len(slots) <= index:
                slots.append({'CpuMetric': 'None', 'GpuMetric': 'None', 'ShowGraph': False})
            parts = str(value).split('|')
            slots[index]['CpuMetric'] = parts[0] if parts else 'None'
            slots[index]['GpuMetric'] = parts[1] if len(parts) > 1 else 'None'
            return
        # Unknown keys are ignored rather than crashing UI paths.
        return

    def _export_fan_policies(self):
        out = {}
        for name, code in MODE_CODES.items():
            slot = self.store.data['Fans'][name]
            mode = int(slot.get('ControlMode', 0) or 0)
            kind = {0: 'Auto', 1: 'Max', 2: 'Custom'}.get(mode, 'Auto')
            if kind != 'Custom':
                out[str(code)] = {'kind': kind}
            else:
                out[str(code)] = {
                    'kind': 'Custom',
                    'delay': int(slot.get('RampUpSeconds', 2) or 2),
                    'stages': slot.get('Stages') or [],
                }
        return out

    def _import_fan_policies(self, fans):
        if not isinstance(fans, dict):
            return
        for code, policy in fans.items():
            name = CODE_TO_NAME.get(str(code))
            if not name or not isinstance(policy, dict):
                continue
            kind = policy.get('kind')
            if kind not in ('Auto', 'Max', 'Custom'):
                continue
            slot = self.store.data['Fans'][name]
            slot['ControlMode'] = {'Auto': 0, 'Max': 1, 'Custom': 2}[kind]
            if kind == 'Custom':
                slot['RampUpSeconds'] = int(policy.get('delay', 2) or 2)
                if policy.get('stages'):
                    slot['Stages'] = policy['stages']

    def _export_power_policies(self):
        out = {}
        for name, code in MODE_CODES.items():
            slot = self.store.data['Tuning'][name]
            if not slot.get('ApplyCpuLimits'):
                continue
            if slot.get('CpuPl1Watts') is None or slot.get('CpuPl2Watts') is None:
                continue
            policy = {'pl1': int(slot['CpuPl1Watts']), 'pl2': int(slot['CpuPl2Watts'])}
            if slot.get('CpuTurboTimeLimitSeconds') is not None:
                policy['tau'] = int(slot['CpuTurboTimeLimitSeconds'])
            if slot.get('CpuBoost') is not None:
                policy['boost'] = bool(slot['CpuBoost'])
            out[str(code)] = policy
        return out

    def _import_power_policies(self, power):
        if not isinstance(power, dict):
            return
        for name in MODE_NAMES:
            self.store.data['Tuning'][name]['ApplyCpuLimits'] = False
        for code, policy in power.items():
            name = CODE_TO_NAME.get(str(code))
            if not name or not isinstance(policy, dict):
                continue
            slot = self.store.data['Tuning'][name]
            slot['ApplyCpuLimits'] = True
            if 'pl1' in policy:
                slot['CpuPl1Watts'] = policy.get('pl1')
            if 'pl2' in policy:
                slot['CpuPl2Watts'] = policy.get('pl2')
            if 'tau' in policy:
                slot['CpuTurboTimeLimitSeconds'] = policy.get('tau')
            if 'boost' in policy:
                slot['CpuBoost'] = bool(policy['boost'])
                slot['CpuBoostMode'] = 1 if policy['boost'] else 0

    def _export_gpu_policies(self):
        out = {}
        for name, code in MODE_CODES.items():
            slot = self.store.data['Tuning'][name]
            if not slot.get('ApplyGpuLimits'):
                continue
            if slot.get('GpuPowerOffsetWatts') is None:
                continue
            out[str(code)] = {
                'ct': int(slot.get('GpuPowerOffsetWatts') or 0),
                'db': int(slot.get('GpuDynamicBoostWatts') or 0),
                'cp': int(slot.get('PlatformPowerOffsetWatts') or 0),
            }
        return out

    def _import_gpu_policies(self, gpu):
        if not isinstance(gpu, dict):
            return
        for name in MODE_NAMES:
            self.store.data['Tuning'][name]['ApplyGpuLimits'] = False
        for code, policy in gpu.items():
            name = CODE_TO_NAME.get(str(code))
            if not name or not isinstance(policy, dict):
                continue
            slot = self.store.data['Tuning'][name]
            slot['ApplyGpuLimits'] = True
            if 'ct' in policy:
                slot['GpuPowerOffsetWatts'] = int(policy['ct'])
            if 'db' in policy:
                slot['GpuDynamicBoostWatts'] = int(policy['db'])
            if 'cp' in policy:
                slot['PlatformPowerOffsetWatts'] = int(policy['cp'])


_MISSING = object()
