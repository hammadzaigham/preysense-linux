import sys,unittest,json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from display import Display
class DisplayTests(unittest.TestCase):
 def test_xwayland_gui_queries_wayland_compositor(self):
  panel=dict(enabled=True,connected=True,name='eDP-1',id=1,currentModeId='1',modes=[dict(id='1',size={'width':2560,'height':1600},refreshRate=240)])
  with patch.dict('display.os.environ',{'QT_QPA_PLATFORM':'xcb','WAYLAND_DISPLAY':'wayland-1'}),patch('display.shutil.which',return_value='/usr/bin/kscreen-doctor'),patch('display.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'outputs':[panel]}))) as run:
   self.assertEqual(Display().snapshot()['current'],'1')
   self.assertEqual(run.call_args.kwargs['env']['QT_QPA_PLATFORM'],'wayland')
   self.assertEqual(run.call_args.kwargs['env']['KSCREEN_BACKEND'],'KSC_KWayland')
 def test_real_x11_session_preserves_backend(self):
  with patch.dict('display.os.environ',{'QT_QPA_PLATFORM':'xcb'},clear=True):self.assertEqual(Display.environment()['QT_QPA_PLATFORM'],'xcb')
