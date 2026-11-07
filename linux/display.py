"""KDE display mode control, restricted to refresh rates at the current resolution."""
import json
import os
import shutil
import subprocess

class Display:
    @staticmethod
    def environment():
        # The GUI uses XWayland for HUD placement, but KScreen must query the
        # compositor that actually owns outputs, not XWayland's virtual screen.
        env=dict(os.environ)
        if env.get('WAYLAND_DISPLAY'):
            env['QT_QPA_PLATFORM']='wayland'
            env['KSCREEN_BACKEND']='KSC_KWayland'
        return env
    def snapshot(self):
        if not shutil.which('kscreen-doctor'): return None
        p=subprocess.run(['kscreen-doctor','-j'],capture_output=True,text=True,timeout=4,env=self.environment())
        if p.returncode: raise RuntimeError('KScreen could not query displays')
        outputs=json.loads(p.stdout).get('outputs',[])
        output=next((o for o in outputs if o.get('enabled') and o.get('connected') and o.get('name','').startswith('eDP')),None)
        if output is None: return None
        current=next((m for m in output['modes'] if m['id']==output['currentModeId']),None)
        if current is None: raise RuntimeError('Current panel mode is unavailable')
        modes=[m for m in output['modes'] if m['size']==current['size']]
        return dict(output=output['id'],current=current['id'],modes=modes)
    def apply(self,mode_id):
        data=self.snapshot()
        if not data or mode_id not in [m['id'] for m in data['modes']]:
            raise ValueError('Refresh mode must belong to the current internal-panel resolution')
        p=subprocess.run(['kscreen-doctor',f'output.{data["output"]}.mode.{mode_id}'],capture_output=True,text=True,timeout=5,env=self.environment())
        if p.returncode: raise RuntimeError(p.stderr.strip() or 'KScreen rejected the display mode')
        if self.snapshot()['current']!=mode_id: raise RuntimeError('Display mode readback failed')
