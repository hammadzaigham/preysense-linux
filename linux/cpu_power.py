"""Intel RAPL power limits through the kernel powercap ABI; transactional readback."""
from pathlib import Path
from tau_encoding import infer_unit_us,windows_endpoint_request_us

class CpuPower:
    def __init__(self,root=Path('/sys/class/powercap')):
        self.root=Path(root)
        self.boost_path=self.root.parents[1]/'devices/system/cpu/intel_pstate/no_turbo'
        self.domains=[]
        self.ceilings=None
        self.time_unit_us=None
        for name in ('intel-rapl:0','intel-rapl-mmio:0'):
            p=self.root/name
            try:
                if (p/'name').read_text().strip()!='package-0': continue
                if (p/'constraint_0_name').read_text().strip()!='long_term': continue
                if (p/'constraint_1_name').read_text().strip()!='short_term': continue
                values=self.read_domain(p)
                self.domains.append(p)
                ceiling=values['pl1'],values['pl2']
                self.ceilings=tuple(min(a,b) for a,b in zip(self.ceilings,ceiling)) if self.ceilings else ceiling
            except (OSError,ValueError): continue
    @staticmethod
    def read_domain(p):
        return dict(pl1=int((p/'constraint_0_power_limit_uw').read_text())/1e6,
                    pl2=int((p/'constraint_1_power_limit_uw').read_text())/1e6,
                    tau=int((p/'constraint_0_time_window_us').read_text())/1e6)
    def boost(self):
        try:return self.boost_path.read_text().strip()=='0'
        except OSError:return None
    def set_boost(self,enabled):
        if type(enabled) is not bool:raise ValueError('CPU boost requires a boolean')
        self.boost_path.write_text('0' if enabled else '1')
        if self.boost()!=enabled:raise RuntimeError('CPU boost readback failed')
    def snapshot(self):
        data={}
        for p in self.domains:
            try: data[p.name]=self.read_domain(p)
            except (OSError,ValueError): pass
        import os
        return dict(domains=data,ceilings=self.ceilings,tau_endpoints=self.time_unit_us is not None,boost=self.boost(),boost_writable=os.access(self.boost_path,os.W_OK),writable=bool(self.domains) and all(os.access(p/name,os.W_OK) for p in self.domains for name in ('constraint_0_power_limit_uw','constraint_1_power_limit_uw')))
    def capture(self):
        return {p.name:self.read_domain(p) for p in self.domains}
    def restore(self,saved):
        errors=[]
        for p in self.domains:
            if p.name not in saved:continue
            for i,key in ((1,'pl2'),(0,'pl1'),(0,'tau')):
                try:
                    value=round(saved[p.name][key]*1000000)
                    file=p/('constraint_0_time_window_us' if key=='tau' else f'constraint_{i}_power_limit_uw')
                    file.write_text(str(value))
                    if abs(int(file.read_text())-value)>125000:raise RuntimeError('readback mismatch')
                except (OSError,ValueError,KeyError,RuntimeError) as exc:errors.append(f'{p.name} {key}: {exc}')
        if errors:raise RuntimeError('CPU power restoration failed: '+'; '.join(errors))
    def apply(self,pl1,pl2,tau=None):
        if not self.domains: raise RuntimeError('Intel RAPL is unavailable')
        if not all(type(v) is int for v in (pl1,pl2)) or not 5<=pl1<=pl2:
            raise ValueError('Use positive integer watts with 5 ≤ PL1 ≤ PL2')
        if tau is not None and (type(tau) is not int or tau not in (0,1,2,4,8,16,32,56,64,128,256,449)):raise ValueError('Unsupported Tau step')
        tau_request=windows_endpoint_request_us(tau,self.time_unit_us) if tau in (0,449) and self.time_unit_us else None
        if tau in (0,449) and tau_request is None:raise RuntimeError('Tau endpoints are unavailable without a verified hardware time unit; choose a numeric window')
        saved={p:self.read_domain(p) for p in self.domains}
        changed=[]
        try:
            for p in self.domains:
                for i,value in ((1,pl2),(0,pl1)):
                    file=p/f'constraint_{i}_power_limit_uw'
                    changed.append((file,int(saved[p][f'pl{i+1}']*1e6)))
                    file.write_text(str(value*1000000))
                    actual=int(file.read_text())
                    if abs(actual-value*1000000)>125000: raise RuntimeError(f'{p.name} PL{i+1} readback failed')
                if tau is not None:
                    file=p/'constraint_0_time_window_us';changed.append((file,round(saved[p]['tau']*1000000)))
                    request=tau_request if tau_request is not None else tau*1000000
                    file.write_text(str(request))
                    if abs(int(file.read_text())-request)>(0 if tau_request is not None else 500000):raise RuntimeError(f'{p.name} Tau readback failed')
        except Exception as exc:
            failures=[]
            for file,value in reversed(changed):
                try: file.write_text(str(value))
                except OSError: failures.append(file.name)
            if failures: raise RuntimeError(f'{exc}; rollback failed for {failures}') from exc
            raise
