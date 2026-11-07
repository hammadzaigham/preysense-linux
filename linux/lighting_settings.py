"""Validated startup replay of explicitly saved lighting, independent of editor focus."""
import re
from hardware import EFFECTS
from lighting_effects import SOFTWARE_EFFECTS

def rgb(value):
    if not isinstance(value,str) or not re.fullmatch('#[0-9a-fA-F]{6}',value):raise ValueError('Invalid saved RGB color')
    return tuple(int(value[i:i+2],16) for i in (1,3,5))
def bounded(settings,key,default,maximum):
    value=int(settings.value(key,default))
    if not 0<=value<=maximum:raise ValueError('Invalid saved lighting range')
    return value
def startup_lighting(settings):
    commands=[]
    if settings.contains('led_timeout'):
        commands.append(('led_timeout',bounded(settings,'led_timeout',0,120)))
    if settings.contains('effect'):
        effect=settings.value('effect','Static')
        if effect not in EFFECTS and effect not in SOFTWARE_EFFECTS:raise ValueError('Unknown saved keyboard effect')
        colors=settings.value('colors',['#28d8ca']*4)
        if not isinstance(colors,(list,tuple)) or len(colors)!=4:raise ValueError('Invalid saved keyboard zones')
        commands.append(('lighting',dict(colors=[rgb(c) for c in colors],effect=effect,brightness=bounded(settings,'brightness',100,100),speed=bounded(settings,'speed',5,10),sync_logo=settings.value('sync_logo',False,type=bool))))
    if settings.contains('logo_effect') and not settings.value('sync_logo',False,type=bool):
        effect=settings.value('logo_effect','Static')
        if effect not in ('Off','Static','Breathing','Neon'):raise ValueError('Unknown saved logo effect')
        commands.append(('logo_lighting',dict(color=rgb(settings.value('logo_color','#28d8ca')),effect=effect,brightness=bounded(settings,'logo_brightness',80,100),speed=bounded(settings,'logo_speed',5,10))))
    return commands
