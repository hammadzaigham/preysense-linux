"""Automatic factory-defaults capture matching Windows DriverFactoryCalibration.

Preferred path: read complete ERM4 profile rows (CPU + GPU) without mode switching.
Fallback: live Acer mode settle via CalibrationCycle (RAPL). PROCHOT and static
CPU floors are captured when readable.
"""
from __future__ import annotations

from pathlib import Path

from gpu_offsets import snap, MAX_CT, MAX_DB, MAX_CP

ROOT = Path('/sys/devices/platform/preysense')
MODE_NAMES = {0: 'Quiet', 1: 'Balanced', 4: 'Performance', 5: 'Turbo', 6: 'Eco'}
MODE_ORDER = (6, 0, 1, 4, 5)  # Eco, Quiet, Balanced, Performance, Turbo


def _snap_gpu(ct, db, cp):
    return snap(ct, MAX_CT), snap(db, MAX_DB), snap(cp, MAX_CP)


def read_erm4_profiles(root=ROOT):
    """Return {mode_name: profile dict} from factory_profiles sysfs, or {}."""
    path = Path(root) / 'factory_profiles'
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {}
    result = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 7:
            continue
        mode, pl1, tau, pl2, ct, db, cp = (int(p) for p in parts)
        name = MODE_NAMES.get(mode)
        if not name or pl1 < 5 or pl2 < pl1 or pl2 > 300:
            continue
        ct, db, cp = _snap_gpu(ct, db, cp)
        result[name] = {
            'CpuPl1Watts': pl1,
            'CpuPl2Watts': pl2,
            'CpuTurboTimeLimitSeconds': int(tau),
            'GpuPowerOffsetWatts': ct,
            'GpuDynamicBoostWatts': db,
            'PlatformPowerOffsetWatts': cp,
        }
    if len(result) != 5:
        return {}
    return result


def capture_prochot_and_static(cpu_power=None, settings=None):
    """Persist global PROCHOT + static RAPL floors into preysense.json Tuning."""
    meta = {}
    try:
        from cpu_prochot import CpuProchot
        prochot = CpuProchot().read()
        if prochot is not None:
            meta['FactoryProchotOffsetCelsius'] = prochot.offset_celsius
            meta['FactoryProchotOffsetLocked'] = prochot.locked
            meta['FactoryTjMaxCelsius'] = prochot.tjmax_celsius
            if settings is not None:
                settings.setValue('factory_prochot_offset', prochot.offset_celsius)
                settings.setValue('factory_prochot_locked', prochot.locked)
                settings.setValue('factory_tjmax', prochot.tjmax_celsius)
    except OSError:
        pass
    if cpu_power is not None:
        try:
            power = cpu_power.snapshot()
            domains = power.get('domains') or {}
            mmio = domains.get('intel-rapl-mmio:0') or domains.get('intel-rapl:0') or {}
            pl1, pl2 = mmio.get('pl1'), mmio.get('pl2')
            if type(pl1) in (int, float) and type(pl2) in (int, float) and 5 <= pl1 <= pl2:
                meta['FactoryStaticCpuPl1Watts'] = int(round(pl1))
                meta['FactoryStaticCpuPl2Watts'] = int(round(pl2))
        except Exception:
            pass
    return meta


def commit_erm4_capture(calibrator, profiles, meta=None, boost=None):
    """Write ERM4 profiles into the calibrator cache / preysense.json."""
    calibrator.begin_batch()
    for name in ('Eco', 'Quiet', 'Balanced', 'Performance', 'Turbo'):
        values = dict(profiles[name])
        if boost is not None:
            values['CpuBoost'] = bool(boost)
        calibrator.stage_profile(
            name,
            values['CpuPl1Watts'],
            values['CpuPl2Watts'],
            values['CpuTurboTimeLimitSeconds'],
            boost=values.get('CpuBoost'),
            gpu=dict(
                ct=values.get('GpuPowerOffsetWatts'),
                db=values.get('GpuDynamicBoostWatts'),
                cp=values.get('PlatformPowerOffsetWatts'),
            ),
        )
    status = calibrator.commit_batch()
    if meta and calibrator.config_store is not None:
        def mutator(cfg):
            tuning = cfg.setdefault('Tuning', {})
            for key, value in meta.items():
                tuning[key] = value
            # Also seed per-mode GPU factory bytes into mode slots when empty.
            for name, profile in profiles.items():
                slot = tuning.setdefault(name, {})
                if slot.get('GpuPowerOffsetWatts') is None:
                    slot['GpuPowerOffsetWatts'] = profile.get('GpuPowerOffsetWatts')
                    slot['GpuDynamicBoostWatts'] = profile.get('GpuDynamicBoostWatts')
                    slot['PlatformPowerOffsetWatts'] = profile.get('PlatformPowerOffsetWatts')
        calibrator.config_store.update(mutator)
    return status


def try_automatic_erm4(calibrator, cpu_power=None, settings=None, root=ROOT):
    """Windows CaptureFromErm4 path. Returns True when all five modes were stored."""
    profiles = read_erm4_profiles(root)
    if not profiles:
        return False
    boost = None
    if cpu_power is not None:
        try:
            snap = cpu_power.snapshot()
            if isinstance(snap.get('boost'), bool):
                boost = snap['boost']
        except Exception:
            pass
    meta = capture_prochot_and_static(cpu_power, settings)
    commit_erm4_capture(calibrator, profiles, meta, boost=boost)
    return not calibrator.needs_calibration()
