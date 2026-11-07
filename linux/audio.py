"""AcerUltraX's documented local control socket; original DTS engine remains external."""
import json,os,socket
from pathlib import Path

class Audio:
    def __init__(self,path=None):self.path=str(path or Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'acerultrax.sock')
    def request(self,command,**values):
        payload=dict(cmd=command,**values)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(2);connection.connect(self.path)
            connection.sendall(json.dumps(payload).encode()+b'\n')
            data=bytearray()
            while b'\n' not in data:
                block=connection.recv(16384)
                if not block:raise RuntimeError('Audio service disconnected')
                data.extend(block)
                if len(data)>1048576:raise RuntimeError('Audio response too large')
        reply=json.loads(data.split(b'\n')[0])
        if not reply.get('ok'):raise RuntimeError(reply.get('error','Audio command failed'))
        return reply.get('result')
    def snapshot(self):
        try:return dict(available=True,status=self.request('status'))
        except (OSError,ValueError,RuntimeError) as exc:return dict(available=False,error=str(exc))
    def command(self,action,values):
        allowed={'set-profile','enable'}
        if action not in allowed:raise ValueError('Unsupported audio action')
        if action=='set-profile':
            name=values.get('name')
            # Apply to active device as well as both speakers and headphones endpoints
            res=None
            for target in (None, '@speakers', '@headphones'):
                try:
                    kwargs = dict(values)
                    if target: kwargs['device'] = target
                    res = self.request('set-profile', **kwargs)
                except Exception: pass
            return res
        if action=='enable':
            for target in (None, '@speakers', '@headphones'):
                try:
                    kwargs = dict(values)
                    if target: kwargs['device'] = target
                    self.request('enable', **kwargs)
                except Exception: pass
            return None
        return self.request(action,**values)
