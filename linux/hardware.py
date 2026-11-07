"""Linux hardware transport. Only explicit, bounded controls are writable."""
from pathlib import Path
import fcntl
import json
import shutil
import subprocess
import time
import errno
from cpu_telemetry import CpuTelemetry

MODES = {'Eco': 6, 'Quiet': 0, 'Balanced': 1, 'Performance': 4, 'Turbo': 5}
EFFECTS = {'Static': 2, 'Breathing': 4, 'Neon': 5, 'Wave': 7, 'Shifting': 7, 'Zoom': 9, 'Meteor': 10, 'Twinkling': 11}

def average_color(colors):
    if not colors:raise ValueError('Colors are required')
    return tuple(round(sum(c[channel] for c in colors)/len(colors)) for channel in range(3))

class Hardware:
    def __init__(self, root=Path('/sys')):
        self.root = Path(root)
        self.bridge = self.root / 'devices/platform/preysense'
        self.last_cpu = None
        self._hid_path=None;self._hid_device=None;self._hid_checked=0
        self.cpu_telemetry=CpuTelemetry(self.root)
        self.ram_speed_mhz = self._detect_ram_speed()

    def _detect_ram_speed(self):
        # Root service exports only the configured transfer rate, not DMI serials.
        if self.root == Path('/sys'):
            try:
                speed=int(Path('/run/preysense-memory/speed_mts').read_text().strip())
                if 0<speed<65535:return speed
            except (OSError,ValueError):pass
        dmi_path = self.root / 'firmware/dmi/tables/DMI'
        if dmi_path.is_file():
            try:
                data = dmi_path.read_bytes()
                offset = 0
                while offset < len(data) - 4:
                    rec_type, rec_len = data[offset], data[offset + 1]
                    if rec_len < 4: break
                    if rec_type == 17:
                        if rec_len >= 0x22:
                            speed = int.from_bytes(data[offset + 0x20:offset + 0x22], 'little')
                            if 0 < speed < 0xFFFF: return speed
                        if rec_len >= 0x17:
                            speed = int.from_bytes(data[offset + 0x15:offset + 0x17], 'little')
                            if 0 < speed < 0xFFFF: return speed
                    idx = offset + rec_len
                    while idx < len(data) - 1 and (data[idx] != 0 or data[idx + 1] != 0):
                        idx += 1
                    offset = idx + 2
            except OSError:
                pass
        import subprocess, re
        try:
            res = subprocess.run(['dmidecode', '-t', '17'], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    m = re.search(r'(?:Configured\s+(?:Memory\s+)?Speed|Speed):\s*(\d+)\s*(?:MT/s|MHz)', line, re.IGNORECASE)
                    if m and int(m.group(1)) > 0:
                        return int(m.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
        # Unknown firmware data must remain unavailable, never guessed.
        return None

    @staticmethod
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None

    def bridge_read(self, name):
        return self.read(self.bridge / name)

    def control_read(self,name):
        cache=getattr(self,'_control_cache',None)
        if cache is None:self._control_cache=cache={}
        if name not in cache:cache[name]=self.bridge_read(name)
        return cache[name]

    def refresh_controls(self):
        self._control_cache={}


    def write(self, name, value):
        allowed = {'profile': set(MODES.values()), 'fan_mode': {0, 1}, 'battery_limit': {80, 100}, 'boot_sound': {0,1}, 'led_timeout': set(range(0, 121)), 'usb_charging': {0,10,20,30}, 'lcd_overdrive': {0,1}}
        if name not in allowed or value not in allowed[name]:
            raise ValueError('Unsupported hardware setting')
        (self.bridge / name).write_text(str(value))
        actual = self.bridge_read(name)
        if not hasattr(self,'_control_cache'):self._control_cache={}
        self._control_cache[name]=actual
        expected = f'{value + 1} {value + 1}' if name == 'fan_mode' else str(value)
        if actual != expected:
            raise RuntimeError(f'Firmware readback mismatch: expected {expected}, got {actual}')

    def fan_duty(self, cpu, gpu):
        if any(type(v) is not int or not 0 <= v <= 100 for v in (cpu,gpu)):
            raise ValueError('Fan duties must be integer percentages from 0 to 100')
        (self.bridge / 'fan_duty').write_text(f'{cpu} {gpu}')

    def hid_device(self):
        if self._hid_path is not None and time.monotonic()-self._hid_checked<5:return self._hid_path
        self._hid_checked=time.monotonic()
        for path in sorted((self.root / 'class/hidraw').glob('hidraw*')):
            info = self.read(path / 'device/uevent') or ''
            if 'HID_ID=0018:00000CF2:00005130' in info and 'ENEK5130' in info:
                self._hid_path=Path('/dev') / path.name
                return self._hid_path
        self._hid_path=None
        return None

    def close_lighting(self):
        device=self._hid_device;self._hid_device=None;self._hid_path=None;self._hid_checked=0
        if device is not None:device.close()

    def _lighting_packets(self,packets):
        # Keyboard and logo share one controller, owned by the worker thread.
        for attempt in range(2):
            try:
                if self._hid_device is None:
                    node=self.hid_device()
                    if node is None:raise RuntimeError('ENEK5130 controller unavailable')
                    self._hid_device=node.open('rb+',buffering=0)
                for packet in packets:fcntl.ioctl(self._hid_device.fileno(),0xc00b4806,packet)
                return
            except OSError as exc:
                self.close_lighting()
                if attempt or exc.errno not in (errno.ENODEV,errno.ENXIO,errno.EIO,errno.EBADF):raise

    def lighting(self, colors, brightness=100, effect='Static', speed=5):
        if len(colors) != 4 or any(len(c) != 3 or any(not 0 <= v <= 255 for v in c) for c in colors):
            raise ValueError('Four RGB colors are required')
        if not 0 <= brightness <= 100 or effect not in EFFECTS or not 0 <= speed <= 10:
            raise ValueError('Invalid lighting parameters')
        packets=[]
        for i,color in enumerate(colors if effect=='Static' else colors[:1]):
            if effect!='Static':color=tuple(round(v*brightness/100) for v in color)
            packets.append(bytes([0xA4,0x21,2 if brightness==0 else EFFECTS[effect],brightness,0 if effect=='Static' or brightness==0 else max(1,speed),0 if effect=='Static' or brightness==0 else 1,*(color if brightness else (0,0,0)),(1<<i) if effect=='Static' else 15,0]))
        self._lighting_packets(packets)

    def logo_lighting(self,color,brightness=100,effect='Static',speed=5):
        effects={'Off':1,'Static':2,'Breathing':4,'Neon':5}
        if effect not in effects or len(color)!=3 or any(type(v) is not int or not 0<=v<=255 for v in color) or not 0<=brightness<=100 or not 0<=speed<=10:
            raise ValueError('Invalid logo lighting parameters')
        off=brightness==0 or effect=='Off'
        packet=bytes([0xa4,0x83,1 if off else effects[effect],0 if off else brightness,0 if off else max(1,min(5,round(speed/2))),0,*(color if not off else (0,0,0)),1,0])
        self._lighting_packets([packet])

    def snapshot(self,requested=None):
        wanted=lambda name:requested is None or name in requested
        result = {name: self.bridge_read(name) if name in ('cpu_temp','gpu_temp','cpu_fan','gpu_fan') and wanted(name) else self.control_read(name) if name not in ('cpu_temp','gpu_temp','cpu_fan','gpu_fan') else None for name in
                  ('cpu_temp', 'gpu_temp', 'cpu_fan', 'gpu_fan', 'profile', 'fan_mode', 'battery_limit', 'boot_sound', 'led_timeout', 'usb_charging')}
        result['lcd_overdrive']=None
        result['model'] = self.read(self.root / 'class/dmi/id/product_name') or 'Unknown system'
        result['bridge'] = self.bridge.exists()
        result['keyboard'] = str(self.hid_device() or '')
        for battery in sorted((self.root / 'class/power_supply').glob('*')):
            if self.read(battery / 'type') == 'Battery':
                result['battery'] = self.read(battery / 'capacity')
                result['battery_status'] = self.read(battery / 'status')
                break
        for sensor in ((self.root / 'class/hwmon').glob('hwmon*') if wanted('cpu_temp') else ()):
            if self.read(sensor / 'name') == 'coretemp':
                if not result['cpu_temp'] or result['cpu_temp'] == '0':
                    val = self.read(sensor / 'temp1_input')
                    result['cpu_temp'] = str(round(int(val)/1000)) if val else None
        try:
            fields = Path('/proc/stat').read_text().splitlines()[0].split()[1:] if wanted('cpu_usage') else []
            times = [int(x) for x in fields[:8]]
            total, idle = sum(times), times[3] + times[4]
            if self.last_cpu:
                dt, di = total-self.last_cpu[0], idle-self.last_cpu[1]
                result['cpu_usage'] = round(100*(dt-di)/dt) if dt else 0
            if fields:self.last_cpu = total, idle
            mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.split()[1].isdigit()} if wanted('memory') else {}
            result['memory'] = round(100*(mem['MemTotal']-mem['MemAvailable'])/mem['MemTotal'])
        except (OSError, ValueError, KeyError, IndexError):
            pass
        result.update(self.cpu_telemetry.snapshot(requested=requested))
        if self.ram_speed_mhz is None and self.root == Path('/sys'):
            try:
                value=int(Path('/run/preysense-memory/speed_mts').read_text().strip())
                if 0<value<65535:self.ram_speed_mhz=value
            except (OSError,ValueError):pass
        result['memory_speed_mhz'] = self.ram_speed_mhz
        return result

    def sensor_snapshot(self,requested):
        """Sensor-only path: never query firmware configuration or power source."""
        result={}
        for name in ('cpu_temp','gpu_temp','cpu_fan','gpu_fan'):
            if name in requested:result[name]=self.bridge_read(name)
        if 'cpu_temp' in requested and not result.get('cpu_temp'):
            for sensor in (self.root/'class/hwmon').glob('hwmon*'):
                if self.read(sensor/'name')=='coretemp':
                    value=self.read(sensor/'temp1_input')
                    result['cpu_temp']=str(round(int(value)/1000)) if value else None
                    break
        if 'cpu_usage' in requested:
            try:
                times=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
                total,idle=sum(times),times[3]+times[4]
                if self.last_cpu:
                    dt,di=total-self.last_cpu[0],idle-self.last_cpu[1]
                    result['cpu_usage']=100*(dt-di)/dt if dt>0 else 0
                self.last_cpu=total,idle
            except (OSError,ValueError,IndexError):result['cpu_usage']=None
        else:self.last_cpu=None
        result.update(self.cpu_telemetry.snapshot(requested=requested))
        if 'memory_speed_mhz' in requested:result['memory_speed_mhz']=self.ram_speed_mhz
        return result

    def gpu_snapshot(self, requested=None):
        if requested is not None and not requested:return {'status':'Idle: no GPU metrics requested'}
        # Never wake a runtime-suspended GPU just to refresh telemetry.
        from gpu_mode import GpuMode
        gpus = GpuMode(self.root).devices()
        nvidia = next((d for d in gpus if d['vendor'] == '0x10de'), None)
        if nvidia and nvidia['runtime'] != 'active':
            return {'name': 'NVIDIA GPU', 'status': 'Sleeping' if nvidia['runtime'] == 'suspended' else 'Power state unavailable', 'runtime': nvidia['runtime'], 'driver': nvidia['driver']}
        if nvidia and nvidia['driver'] != 'nvidia':
            return {'status': 'NVIDIA driver not active; restart after installation', 'driver': nvidia['driver']}

        # Fastest/cheapest route: direct in-process NVML via ctypes (sub-millisecond, zero-fork)
        # Only used against live system hardware (/sys)
        if hasattr(self, 'root') and self.root == Path('/sys'):
            try:
                from nvml_telemetry import NvmlTelemetry
                nvml = NvmlTelemetry.get_instance()
                if nvml.available:
                    metrics = nvml.read_metrics(requested)
                    if metrics is not None:
                        return metrics
            except Exception:
                pass

        if not shutil.which('nvidia-smi'):
            return {'status': 'NVIDIA driver tools unavailable'}
        try:
            columns={'name':'name','temperature':'temperature.gpu','usage':'utilization.gpu','power':'power.draw','clock':'clocks.gr','memory_clock_mhz':'clocks.mem','memory_used_gb':'memory.used','memory_total_gb':'memory.total','default_power_limit_w':'power.default_limit','max_power_limit_w':'power.max_limit'}
            keys=[key for key in columns if requested is None or key=='name' or key in requested]
            p=subprocess.run(['nvidia-smi','--query-gpu='+','.join(columns[k] for k in keys),'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
            if p.returncode:return {'status':'NVIDIA GPU unavailable'}
            values=[v.strip() for v in p.stdout.splitlines()[0].split(',')]
            data=dict(zip(keys,values))
            import math
            for key in ('memory_used_gb','memory_total_gb','default_power_limit_w','max_power_limit_w'):
                if key not in keys:continue
                try:value=float(data.get(key,''))
                except ValueError:value=float('nan')
                data[key]=round(value/1024,3) if key.startswith('memory_') and math.isfinite(value) and value>=0 else value if math.isfinite(value) and value>0 else None
            return data
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            return {'status': 'NVIDIA GPU unavailable'}

if __name__ == '__main__':
    h = Hardware()
    print(json.dumps(dict(h.snapshot(), gpu=h.gpu_snapshot()), indent=2))
