"""Publish only configured RAM transfer rate from root-readable SMBIOS Type 17."""
from pathlib import Path

OUTPUT = Path('/run/preysense-memory/speed_mts')

def configured_speed(data):
    speeds=[];offset=0
    while offset+4<=len(data):
        kind,length=data[offset],data[offset+1]
        if length<4 or offset+length>len(data):break
        if kind==17 and length>=0x22:
            size=int.from_bytes(data[offset+0x0c:offset+0x0e],'little')
            speed=int.from_bytes(data[offset+0x20:offset+0x22],'little')
            if size and 0<speed<0xffff:speeds.append(speed)
        if kind==127:break
        end=data.find(b'\0\0',offset+length)
        if end<0:break
        offset=end+2
    return min(speeds) if speeds else None

def publish(source=Path('/sys/firmware/dmi/tables/DMI'),target=OUTPUT):
    speed=configured_speed(source.read_bytes())
    if speed is None:
        target.unlink(missing_ok=True)
        return None
    target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    temporary=target.with_suffix('.tmp')
    temporary.write_text(f'{speed}\n');temporary.chmod(0o444);temporary.replace(target)
    return speed

if __name__=='__main__':publish()
