import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop_session import configure_platform
class DesktopSessionTests(unittest.TestCase):
 def test_wayland_kde_uses_available_xwayland(self):
  env={'WAYLAND_DISPLAY':'wayland-1','DISPLAY':':0','XDG_CURRENT_DESKTOP':'KDE'}
  self.assertEqual(configure_platform(env),'xcb');self.assertEqual(env['QT_QPA_PLATFORM'],'xcb')
 def test_explicit_backend_is_preserved(self):
  env={'WAYLAND_DISPLAY':'wayland-1','DISPLAY':':0','XDG_CURRENT_DESKTOP':'KDE','QT_QPA_PLATFORM':'wayland'}
  self.assertEqual(configure_platform(env),'wayland')
 def test_no_x_display_or_non_kde_is_unchanged(self):
  for env in ({'WAYLAND_DISPLAY':'wayland-1','XDG_CURRENT_DESKTOP':'KDE'},{'WAYLAND_DISPLAY':'wayland-1','DISPLAY':':0','XDG_CURRENT_DESKTOP':'GNOME'}):
   self.assertIsNone(configure_platform(env));self.assertNotIn('QT_QPA_PLATFORM',env)
