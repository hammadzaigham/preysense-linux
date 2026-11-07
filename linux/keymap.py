"""Save/restore only the PHN16S Predator key mappings; root installer utility."""
import argparse,fcntl,json,struct
from pathlib import Path
SCANS=(0x75,0xf5)
def keyboard(root=Path('/sys/class/input')):
    for event in root.glob('event*'):
        try:
            if (event/'device/name').read_text().strip()=='AT Translated Set 2 keyboard':return Path('/dev/input')/event.name
        except OSError:pass
    raise RuntimeError('Built-in atkbd device not found')
def get(fd,scan):
    data=bytearray(struct.pack('II',scan,0));fcntl.ioctl(fd,0x80084504,data,True);return struct.unpack('II',data)[1]
def save(path):
    path=Path(path)
    if path.exists():return
    with keyboard().open('rb',buffering=0) as device:values={str(s):get(device.fileno(),s) for s in SCANS}
    source='captured-before-install'
    # Migration from this development install: both original values were read
    # before the first hwdb write (75=0, f5=425), but not persisted at that time.
    if values=={'117':202,'245':202} and Path('/etc/udev/hwdb.d/90-preysense-keyboard.hwdb').exists():
        values={'117':0,'245':425};source='verified-pre-first-install-PHN16S-71-baseline'
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(dict(values=values,source=source)));temp.chmod(0o600);temp.replace(path)
def restore(path):
    path=Path(path)
    if not path.exists():return
    data=json.loads(path.read_text());values=data['values']
    if set(values)!={str(s) for s in SCANS} or any(type(v) is not int or not 0<=v<=767 for v in values.values()):raise ValueError('Invalid saved Predator map')
    with keyboard().open('rb',buffering=0) as device:
        for scan in SCANS:
            fcntl.ioctl(device.fileno(),0x40084504,struct.pack('II',scan,values[str(scan)]))
            if get(device.fileno(),scan)!=values[str(scan)]:raise RuntimeError('Predator key-map restoration failed')
    path.unlink()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['save','restore']);parser.add_argument('--file',default='/var/lib/preysense/keymap.json');args=parser.parse_args()
    (save if args.action=='save' else restore)(args.file)
