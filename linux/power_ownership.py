"""Restore session RAPL edits only while fields still match PreySense's last write."""
class PowerOwnership:
    def __init__(self,power):self.power=power;self.original={};self.expected={}
    def apply(self,**values):
        before=self.power.capture()
        self.power.apply(**values)
        after=self.power.capture()
        for domain,fields in before.items():
            for key,value in fields.items():
                token=(domain,key)
                if after.get(domain,{}).get(key)!=value:
                    if token not in self.original or self.expected.get(token)!=value:self.original[token]=value
                    self.expected[token]=after[domain][key]
    def release(self):
        current=self.power.capture();restore={};preserved=[]
        for (domain,key),expected in self.expected.items():
            actual=current.get(domain,{}).get(key)
            if actual==expected:
                restore.setdefault(domain,dict(current[domain]))[key]=self.original[(domain,key)]
            else:preserved.append(f'{domain} {key}')
        if restore:self.power.restore(restore)
        self.original.clear();self.expected.clear()
        return preserved
    def forget(self):self.original.clear();self.expected.clear()
