"""Explicit desktop-user hardware access for an installed RPM, run with sudo."""
import os,pwd,re,subprocess,sys
from pathlib import Path

def configure(user):
    if os.geteuid()!=0:raise SystemExit('Administrator access is required for hardware permissions')
    account=pwd.getpwnam(user)
    if account.pw_uid==0:raise SystemExit('Select a non-root desktop user')
    if Path('/sys/class/dmi/id/product_name').read_text().strip()!='Predator PHN16S-71':raise SystemExit('This hardware bridge supports PHN16S-71 only')
    import grp
    group=grp.getgrgid(account.pw_gid).gr_name
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_-]*\$?',group):raise SystemExit('Unsupported primary group name')
    drop=Path('/etc/systemd/system/preysense-hardware.service.d');drop.mkdir(parents=True,exist_ok=True)
    (drop/'desktop-user.conf').write_text(f'[Service]\nEnvironment=PREYSENSE_GROUP={group}\n')
    # A package default rule grants the private preysense group; this higher
    # priority local rule grants only the explicitly configured desktop group.
    Path('/etc/udev/rules.d/71-preysense-desktop.rules').write_text(f'SUBSYSTEM=="hidraw", KERNELS=="0018:0CF2:5130.*", GROUP="{group}", MODE="0660"\nSUBSYSTEM=="hidraw", KERNELS=="0018:1025:174B.*", GROUP="{group}", MODE="0640"\n')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    # Do not unload/reload a loaded module or disturb an active fan controller.
    subprocess.run(['systemctl','start','preysense-hardware.service'],check=True)
    subprocess.run(['/opt/preysense/hardware-permissions.sh',group],check=True)
    subprocess.run(['udevadm','control','--reload-rules'],check=True)
    subprocess.run(['udevadm','trigger','--subsystem-match=hidraw'],check=True)
    from service_lifecycle import configure as configure_services
    configure_services(user)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable', 'preysense-hardware.service'],check=True)
def cleanup():
    from service_lifecycle import cleanup as cleanup_services
    cleanup_services()
    if os.geteuid()!=0:raise SystemExit('Root required')
    for name in ('/etc/systemd/system/preysense-hardware.service.d/desktop-user.conf','/etc/udev/rules.d/71-preysense-desktop.rules'):
        Path(name).unlink(missing_ok=True)
    for domain in ('intel-rapl:0','intel-rapl-mmio:0'):
        for field in ('constraint_0_power_limit_uw','constraint_1_power_limit_uw','constraint_0_time_window_us','energy_uj'):
            path=Path('/sys/class/powercap')/domain/field
            if path.exists():
                os.chown(path,0,0);path.chmod(path.stat().st_mode & ~0o060)
    path=Path('/sys/devices/system/cpu/intel_pstate/no_turbo')
    if path.exists():os.chown(path,0,0);path.chmod(path.stat().st_mode & ~0o020)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: rpm_configure.py DESKTOP_USER')
    if sys.argv[1]=='--remove':cleanup()
    else:configure(sys.argv[1])
