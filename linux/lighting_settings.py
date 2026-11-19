"""Validated startup replay of explicitly saved lighting, independent of editor focus."""
import re
from hardware import EFFECTS
from lighting_effects import SOFTWARE_EFFECTS
from mode_key_lighting import color_for, hex_to_rgb


def mode_palette(lighting, profile):
    """Translate the shared operating-mode palette to a Linux static RGB value."""
    color = color_for(1 if profile is None else profile, lighting.get('PowerModeColors', {}))
    brightness = max(0, min(100, int(lighting.get('ModeBrightness', 100))))
    return hex_to_rgb(color), brightness


def step_keyboard_brightness(brightness, steps):
    """Move to the next firmware 25% rung in the requested direction."""
    brightness = max(0, min(100, int(brightness)))
    if not steps:
        return brightness
    rung = brightness // 25 if steps > 0 else (brightness + 24) // 25
    return max(0, min(100, (rung + steps) * 25))

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
        effect=settings.value('effect','Mode')
        if effect not in (*EFFECTS, *SOFTWARE_EFFECTS, 'Mode'):raise ValueError('Unknown saved keyboard effect')
        colors=settings.value('colors',['#00AEC7']*2+['#00E5FF']*2)
        if not isinstance(colors,(list,tuple)) or len(colors)!=4:raise ValueError('Invalid saved keyboard zones')
        payload = dict(colors=[rgb(c) for c in colors], effect=effect,
                       brightness=bounded(settings,'brightness',100,100), speed=bounded(settings,'speed',5,10),
                       sync_logo=settings.value('sync_logo',False,type=bool))
        if effect == 'Wave':
            payload['direction'] = bounded(settings, 'lighting_direction', 1, 3)
        commands.append(('lighting', payload))
    if settings.contains('logo_effect') and not settings.value('sync_logo',False,type=bool):
        effect=settings.value('logo_effect','Mode')
        if effect not in ('Off','Static','Breathing','Neon','Mode'):raise ValueError('Unknown saved logo effect')
        commands.append(('logo_lighting',dict(color=rgb(settings.value('logo_color','#00AEC7')),effect=effect,brightness=bounded(settings,'logo_brightness',100,100),speed=bounded(settings,'logo_speed',5,10))))
    if settings.contains('mode_key_effect') or settings.contains('mode_key_color'):
        effect=settings.value('mode_key_effect','Mode')
        if effect not in ('Off','Static','Breathing','Neon','Wave','Zoom','Mode'):raise ValueError('Unknown saved mode key effect')
        color=rgb(settings.value('mode_key_color','#00AEC7'))
        sync=settings.value('mode_key_sync',False,type=bool)
        commands.append(('mode_key_lighting',dict(color=color,effect=effect,brightness=bounded(settings,'mode_key_brightness',100,100),speed=bounded(settings,'mode_key_speed',5,10),sync=sync)))
    return commands
