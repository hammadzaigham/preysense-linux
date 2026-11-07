"""Validate saved per-mode policies before they reach hardware transports."""
from hardware import MODES
from fan_curve import FanCurve

def fan_policy(policy):
    if not isinstance(policy,dict) or policy.get('kind') not in ('Auto','Max','Custom'):
        raise ValueError('Invalid fan policy')
    if policy['kind']=='Custom':
        FanCurve(policy['cpu'],policy['gpu'],policy['delay'])
    return dict(policy)

def power_policy(policy):
    if not isinstance(policy,dict) or not {'pl1','pl2'}<=set(policy) or bool(set(policy)-{'pl1','pl2','tau','boost'}):
        raise ValueError('Invalid CPU power policy')
    if any(type(policy[k]) is not int for k in ('pl1','pl2')) or not 5<=policy['pl1']<=policy['pl2']:
        raise ValueError('CPU limits require 5 ≤ PL1 ≤ PL2')
    if 'tau' in policy and (type(policy['tau']) is not int or policy['tau'] not in (0,1,2,4,8,16,32,56,64,128,256,449)):raise ValueError('Unsupported Tau step')
    if 'boost' in policy and type(policy['boost']) is not bool:raise ValueError('CPU boost must be boolean')
    return dict(policy)

def policies(values,validate):
    if not isinstance(values,dict):raise ValueError('Mode policies must be an object')
    result={}
    for key,value in values.items():
        if str(key) not in {str(v) for v in MODES.values()}:raise ValueError('Unknown performance mode')
        result[str(key)]=validate(value)
    return result
