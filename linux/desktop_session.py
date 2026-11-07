"""Choose the Qt backend that supports explicit desktop HUD placement."""
import os

def configure_platform(environment=None):
    env=os.environ if environment is None else environment
    # Qt Wayland xdg-shell does not permit an application to position its own
    # top-level surfaces. KDE's existing XWayland supports these HUD coordinates.
    # Respect an explicit backend (including offscreen tests or native Wayland).
    if env.get('QT_QPA_PLATFORM'):
        return env['QT_QPA_PLATFORM']
    desktop=env.get('XDG_CURRENT_DESKTOP','').lower().split(':')
    if env.get('WAYLAND_DISPLAY') and env.get('DISPLAY') and 'kde' in desktop:
        env['QT_QPA_PLATFORM']='xcb'
        return 'xcb'
    return None
