"""Resolve per-mode Intel editor values from saved policy or observed baseline."""
import math
TAU_STEPS=(0,1,2,4,8,16,32,56,64,128,256,449)

def observed_policy(cpu):
    domains=cpu.get('domains',{}) if isinstance(cpu,dict) else {}
    # Prefer MMIO limits directly when available, otherwise fall back to any valid domain
    mmio=domains.get('intel-rapl-mmio:0') or domains.get('mmio')
    if isinstance(mmio,dict) and all(type(mmio.get(k)) in (int,float) and math.isfinite(mmio[k]) and mmio[k]>=0 for k in ('pl1','pl2','tau')):
        return dict(pl1=round(mmio['pl1']),pl2=round(mmio['pl2']),tau=min(TAU_STEPS,key=lambda step:abs(step-mmio['tau'])))
    values=[v for v in domains.values() if isinstance(v,dict) and all(type(v.get(k)) in (int,float) and math.isfinite(v[k]) and v[k]>=0 for k in ('pl1','pl2','tau'))]
    if not values:return None
    return dict(pl1=round(min(v['pl1'] for v in values)),pl2=round(min(v['pl2'] for v in values)),tau=min(TAU_STEPS,key=lambda step:abs(step-min(v['tau'] for v in values))))
