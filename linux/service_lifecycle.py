"""Bounded lifecycle for the single PreySense hardware helper."""
import os,subprocess,pwd,json
from pathlib import Path
UNITS=('preysense-hardware.service',)
CONFIG=Path('/usr/lib/preysense/service-lifecycle.json') if Path('/usr/lib/preysense').exists() else Path('/opt/preysense/linux/service-lifecycle.json')

def marker():return Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'preysense-running'

def start_helpers():
    # Installer supplies a rule allowing only this fixed start/stop operation.
    if not CONFIG.exists():return False
    if json.loads(CONFIG.read_text()).get('uid')!=os.getuid():return False
    path=marker();path.touch(mode=0o600)
    try:subprocess.run(['systemctl','--no-ask-password','start',*UNITS],check=True,capture_output=True,text=True,timeout=15)
    except Exception:
        path.unlink(missing_ok=True);raise
    return True

def stop_helpers():
    if CONFIG.exists():
        subprocess.run(['systemctl','--no-ask-password','stop',*UNITS],check=False,capture_output=True,text=True,timeout=15)
    marker().unlink(missing_ok=True)

def configure(user):
    if os.geteuid()!=0:raise SystemExit('Administrator access required for helper setup')
    account=pwd.getpwnam(user)
    if account.pw_uid==0:raise SystemExit('Select the desktop user')
    for unit in UNITS:
        directory=Path('/etc/systemd/system')/(unit+'.d');directory.mkdir(parents=True,exist_ok=True)
        # Either the login autostart preference or an explicit manual launch.
        text='[Unit]\nConditionPathExists=|'+account.pw_dir+'/.config/autostart/preysense.desktop\nConditionPathExists=|/run/user/'+str(account.pw_uid)+'/preysense-running\n'
        (directory/'startup-preference.conf').write_text(text)
    rules=Path('/etc/polkit-1/rules.d/49-preysense-services.rules')
    rules.write_text('polkit.addRule(function(action, subject) {\n'
        '  if (action.id === "org.freedesktop.systemd1.manage-units" && subject.local && subject.active && subject.user === '+json.dumps(user)+' &&\n'
        '      '+json.dumps(list(UNITS))+'.indexOf(action.lookup("unit")) !== -1 &&\n'
        '      ["start", "stop"].indexOf(action.lookup("verb")) !== -1) { return polkit.Result.YES; }\n});\n')
    rules.chmod(0o644)
    CONFIG=Path('/usr/lib/preysense/service-lifecycle.json') if Path('/usr/lib/preysense').exists() else Path('/opt/preysense/linux/service-lifecycle.json')
    CONFIG.write_text(json.dumps({'uid':account.pw_uid}))
    CONFIG.chmod(0o644)

def cleanup():
    for cfg in (Path('/usr/lib/preysense/service-lifecycle.json'), Path('/opt/preysense/linux/service-lifecycle.json')):
        cfg.unlink(missing_ok=True)
    for unit in UNITS:
        p=Path('/etc/systemd/system')/(unit+'.d')/'startup-preference.conf';p.unlink(missing_ok=True)
    Path('/etc/polkit-1/rules.d/49-preysense-services.rules').unlink(missing_ok=True)

if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--remove']:cleanup()
    elif len(sys.argv)==2:configure(sys.argv[1])
    else:raise SystemExit('Usage: service_lifecycle.py DESKTOP_USER | --remove')
