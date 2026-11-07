"""Read-only kernel CPU frequency and RAPL package-power samples.

No MSR access, privilege escalation or energy-counter permission changes occur
here. Frequency is the kernel's scaling frequency, not a measured effective clock.
Power is an energy-counter delta; unavailable/unsafe samples return None.
"""
import math,re,time
from pathlib import Path

class CpuTelemetry:
    def __init__(self,root=Path('/sys'),clock=time.monotonic,max_interval=5.0,max_power_w=1000.0,procroot=Path('/proc')):
        self.root=Path(root);self.procroot=Path(procroot);self.clock=clock;self.previous=None
        self.cpu_previous={};self.cpu_previous_time=None
        self._hybrid_signature=None;self._hybrid_groups=None
        self.max_interval=float(max_interval);self.max_power_w=float(max_power_w)
    @staticmethod
    def read_int(path):
        try:return int(path.read_text().strip())
        except (OSError,ValueError):return None
    @staticmethod
    def parse_cpu_list(text):
        """Strict kernel cpulist syntax; malformed data is not a topology guess."""
        text=text.strip()
        if not text:return set()
        result=set()
        for part in text.split(','):
            if not re.fullmatch(r'[0-9]+(?:-[0-9]+)?',part):return None
            bounds=part.split('-');start=int(bounds[0]);end=int(bounds[-1])
            if end<start or end>1048575 or end-start>65535:return None
            result.update(range(start,end+1))
        return result
    def online_cpus(self):
        path=self.root/'devices/system/cpu/online'
        try:return self.parse_cpu_list(path.read_text()) or set()
        except OSError:return None
    def frequencies(self):
        values={};online=self.online_cpus()
        for cpu in (self.root/'devices/system/cpu').glob('cpu[0-9]*'):
            if not cpu.name[3:].isdigit():continue
            index=int(cpu.name[3:])
            if online is not None and index not in online:continue
            if self.read_int(cpu/'online')==0:continue
            value=self.read_int(cpu/'cpufreq/scaling_cur_freq')
            if value is not None and 0<value<=10000000:values[index]=value/1000
        return values
    @staticmethod
    def average(values):return round(sum(values)/len(values),1) if values else None
    def frequency_mhz(self):return self.average(list(self.frequencies().values()))
    def hybrid_cpus(self):
        paths=[self.root/'bus/event_source/devices'/name/'cpus' for name in ('cpu_core','cpu_atom')]
        def signature(path):
            try:
                stat=path.stat();return stat.st_mtime_ns,stat.st_size,stat.st_ino
            except OSError:return None
        current=tuple(signature(path) for path in paths)
        if self._hybrid_groups is not None and current==self._hybrid_signature:
            return tuple(set(group) if group is not None else None for group in self._hybrid_groups)
        groups=[]
        for name in ('cpu_core','cpu_atom'):
            try:group=self.parse_cpu_list((self.root/'bus/event_source/devices'/name/'cpus').read_text())
            except OSError:group=None
            groups.append(group)
        if groups[0] and groups[1] and groups[0]&groups[1]:groups=[None,None]
        self._hybrid_signature=current;self._hybrid_groups=tuple(groups)
        return tuple(groups)
    def core_usage(self):
        now=self.clock();current={};online=self.online_cpus()
        try:lines=(self.procroot/'stat').read_text().splitlines()
        except OSError:lines=[]
        for line in lines:
            fields=line.split()
            if not fields or not re.fullmatch(r'cpu[0-9]+',fields[0]) or len(fields)<5:continue
            try:values=tuple(int(v) for v in fields[1:9])
            except ValueError:continue
            index=int(fields[0][3:])
            if any(v<0 for v in values) or (online is not None and index not in online):continue
            if self.read_int(self.root/f'devices/system/cpu/cpu{index}/online')==0:continue
            current[index]=values
        previous=self.cpu_previous;previous_time=self.cpu_previous_time
        self.cpu_previous=current;self.cpu_previous_time=now
        if not isinstance(now,(int,float)) or not math.isfinite(now):
            self.cpu_previous={};self.cpu_previous_time=None;return {}
        if previous_time is None or not 0<now-previous_time<=self.max_interval:return {}
        result={}
        for index,values in current.items():
            old=previous.get(index)
            if old is None or len(old)!=len(values):continue
            delta=[new-before for new,before in zip(values,old)]
            if any(v<0 for v in delta):continue
            total=sum(delta)
            if total<=0:continue
            idle=delta[3]+(delta[4] if len(delta)>4 else 0)
            result[index]=round(100*(total-idle)/total,1)
        return result
    def memory_used_gb(self):
        try:lines=(self.procroot/'meminfo').read_text().splitlines()
        except OSError:return None
        values={}
        for line in lines:
            match=re.fullmatch(r'(MemTotal|MemAvailable):\s+([0-9]+)\s+kB\s*',line)
            if match:values[match[1]]=int(match[2])
        total=values.get('MemTotal');available=values.get('MemAvailable')
        if total is None or available is None or total<=0 or not 0<=available<=total:return None
        return round((total-available)/1024**2,2)
    def package_counter(self):
        for name in ('intel-rapl:0','intel-rapl-mmio:0'):
            domain=self.root/'class/powercap'/name
            try:
                if (domain/'name').read_text().strip()!='package-0':continue
            except OSError:continue
            energy=self.read_int(domain/'energy_uj');maximum=self.read_int(domain/'max_energy_range_uj')
            if energy is not None and maximum is not None and maximum>0 and 0<=energy<maximum:
                return (name,energy,maximum)
        return None
    def power_w(self):
        sample=self.package_counter()
        now=self.clock()
        if sample is None or not isinstance(now,(int,float)) or not math.isfinite(now):
            self.previous=None;return None
        domain,energy,maximum=sample;previous=self.previous
        self.previous=(domain,energy,maximum,now)
        if previous is None or previous[0]!=domain or previous[2]!=maximum:return None
        interval=now-previous[3]
        if not math.isfinite(interval) or interval<=0 or interval>self.max_interval:return None
        delta=energy-previous[1]
        if delta<0:delta+=maximum
        watts=delta/1000000/interval
        if not math.isfinite(watts) or watts<=0 or watts>self.max_power_w:return None
        rounded=round(watts,2)
        return rounded if rounded>0 else None
    def snapshot(self,requested=None):
        """None preserves full sampling; an empty set performs no sensor reads."""
        req=set(requested) if requested is not None else None
        wants=lambda key:req is None or key in req
        frequency_fields={'cpu_frequency_mhz','cpu_p_core_mhz','cpu_e_core_mhz'}
        usage_fields={'cpu_max_core_usage','cpu_p_core_usage','cpu_e_core_usage'}
        group_fields={'cpu_p_core_mhz','cpu_e_core_mhz','cpu_p_core_usage','cpu_e_core_usage'}
        frequencies=self.frequencies() if req is None or req&frequency_fields else {}
        pcores,ecores=self.hybrid_cpus() if req is None or req&group_fields else (None,None)
        if req is None or req&usage_fields:usage=self.core_usage()
        else:
            usage={};self.cpu_previous={};self.cpu_previous_time=None
        def group_mean(values,group):
            return self.average([value for index,value in values.items() if index in group]) if group else None
        if wants('cpu_power_w'):power=self.power_w()
        else:power=None;self.previous=None
        data=dict(cpu_frequency_mhz=self.average(list(frequencies.values())),cpu_power_w=power,
                  cpu_p_core_mhz=group_mean(frequencies,pcores),cpu_e_core_mhz=group_mean(frequencies,ecores),
                  cpu_max_core_usage=max(usage.values()) if usage else None,
                  cpu_p_core_usage=group_mean(usage,pcores),cpu_e_core_usage=group_mean(usage,ecores),
                  memory_used_gb=self.memory_used_gb() if wants('memory_used_gb') else None)
        if req is not None:
            for key in data:
                if key not in req:data[key]=None
        return data
