"""Missing-only observed runtime calibration cache; pure dictionary of mode limits."""
import copy,json,math,os,tempfile,uuid
from pathlib import Path
import fcntl

MODES={0:'Quiet',1:'Balanced',4:'Performance',5:'Turbo',6:'Eco'}
MAX_BYTES=262144

def _number(value,maximum):
    return value if type(value) in (int,float) and math.isfinite(value) and 0<=value<=maximum else None

class Calibrator:
    def __init__(self,path=None,root=Path('/sys')):
        base=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
        self.path=Path(path) if path is not None else base/'PreySense/calibration.json'
        self.root=Path(root);self.identity={}
        self.cache,self.corrupt=self._load()

    def _load(self):
        try:
            if self.path.is_symlink():raise ValueError('Calibration symlink is not accepted')
            if self.path.stat().st_size>MAX_BYTES:raise ValueError('Calibration too large')
            data=json.loads(self.path.read_text(),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            if not isinstance(data,dict):raise ValueError('Calibration schema')
            valid={}
            for mode_name,values in data.items():
                if mode_name in MODES.values() and isinstance(values,dict):
                    pl1=_number(values.get('pl1'),2000)
                    pl2=_number(values.get('pl2'),2000)
                    tau=_number(values.get('tau'),4000000)
                    if pl1 is not None and pl2 is not None and tau is not None:
                        valid[mode_name]={'pl1':float(pl1),'pl2':float(pl2),'tau':float(tau)}
            return valid,False
        except FileNotFoundError:return {},False
        except (OSError,ValueError,UnicodeError,RecursionError):return {},True

    @staticmethod
    def _mode(value):
        if value in MODES.values():return value
        if type(value) is int:return MODES.get(value)
        if isinstance(value,str) and value.isdigit():return MODES.get(int(value))
        return None

    @staticmethod
    def _complete(profile):
        if not isinstance(profile,dict):return False
        return all(type(profile.get(k)) in (int,float) and math.isfinite(profile[k]) and profile[k]>=0 for k in ('pl1','pl2','tau'))

    def _status(self,mode,count=0,written=False,error=None):
        ready=bool(mode and self._complete(self.cache.get(mode)))
        return dict(state='ready' if ready else 'partial',ready=ready,newfilled=count,written=written,current_profile=mode,
                    missing_profiles=[name for name in ('Eco','Quiet','Balanced','Performance','Turbo') if not self._complete(self.cache.get(name))],
                    error=error)

    def has_profile(self):
        return any(self._complete(p) for p in self.cache.values())

    def missing_modes(self):
        return [name for name in ('Eco','Quiet','Balanced','Performance','Turbo')
                if not self._complete(self.cache.get(name))]

    def needs_calibration(self):
        return bool(self.missing_modes())

    def update(self,data):
        if not isinstance(data,dict):return self._status(None)
        mode=self._mode(data.get('profile'))
        if not mode:return self._status(None)
        if self._complete(self.cache.get(mode)):return self._status(mode)

        # Extract mmio limits from data
        power=data.get('cpu_power') if isinstance(data.get('cpu_power'),dict) else {}
        domains=power.get('domains') if isinstance(power.get('domains'),dict) else {}
        mmio=domains.get('intel-rapl-mmio:0') or domains.get('mmio')
        if not isinstance(mmio,dict):
            # fallback if single domain or raw
            mmio=domains.get('intel-rapl:0') if isinstance(domains.get('intel-rapl:0'),dict) else {}
        pl1=_number(mmio.get('pl1'),2000)
        pl2=_number(mmio.get('pl2'),2000)
        tau=_number(mmio.get('tau'),4000000)
        if pl1 is None or pl2 is None or tau is None:
            return self._status(mode)

        profile={'pl1':float(pl1),'pl2':float(pl2),'tau':float(tau)}
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with (self.path.parent/(self.path.name+'.lock')).open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                latest,corrupt=self._load()
                if self._complete(latest.get(mode)):
                    self.cache=latest
                    return self._status(mode)
                latest[mode]=profile
                encoded=json.dumps(latest,indent=2,sort_keys=True).encode()
                if len(encoded)>MAX_BYTES:raise ValueError('Calibration size limit reached')
                if corrupt and self.path.exists():self.path.replace(self.path.with_name(self.path.name+'.corrupt-'+uuid.uuid4().hex))
                temporary=None
                try:
                    with tempfile.NamedTemporaryFile(dir=self.path.parent,prefix='.calibration-',delete=False) as stream:
                        temporary=Path(stream.name);os.chmod(temporary,0o600);stream.write(encoded);stream.flush();os.fsync(stream.fileno())
                    os.replace(temporary,self.path);temporary=None
                    directory=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
                    try:os.fsync(directory)
                    finally:os.close(directory)
                finally:
                    if temporary is not None:temporary.unlink(missing_ok=True)
                self.cache=latest;self.corrupt=False
            return self._status(mode,count=1,written=True)
        except (OSError,ValueError) as exc:return self._status(mode,error=str(exc))
