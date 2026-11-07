"""Install an app-scoped KWin instant-window effect in the current user's account."""
import os
from pathlib import Path
import shutil
import subprocess

PLUGIN = 'preysense-instant'
SOURCE = Path(__file__).parent/'kwin'/PLUGIN

def install_instant_effect(source=SOURCE):
    """Return status; never disable global compositor effects or install packages.

    Call once before showing windows. The packaged source is required in installed
    runtimes too. Offscreen tests/non-KDE sessions perform no external changes.
    """
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        return dict(available=False, reason='Offscreen platform')
    desktop=os.environ.get('XDG_CURRENT_DESKTOP','').lower()
    if 'kde' not in desktop:
        return dict(available=False, reason='KWin integration is KDE-specific')
    package=Path(source)
    if not (package/'metadata.json').is_file():
        return dict(available=False, reason='PreySense KWin package missing')
    for command in ('kpackagetool6','kwriteconfig6','busctl'):
        if shutil.which(command) is None:
            return dict(available=False, reason=f'{command} unavailable')
    data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
    target=data/'kwin/effects'/PLUGIN
    try:
        same=target.is_dir() and all((target/path.relative_to(package)).is_file() and
            (target/path.relative_to(package)).read_bytes()==path.read_bytes()
            for path in package.rglob('*') if path.is_file())
        if not same:
            action='--upgrade' if target.exists() else '--install'
            subprocess.run(['kpackagetool6','--type','KWin/Effect',action,str(package)],
                check=True,capture_output=True,text=True,timeout=8)
        config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'kwinrc'
        backup=config.with_name('kwinrc.before-preysense-instant')
        if config.exists() and not backup.exists():shutil.copy2(config,backup)
        subprocess.run(['kwriteconfig6','--file','kwinrc','--group','Plugins','--key',
                        PLUGIN+'Enabled','true'],check=True,capture_output=True,timeout=3)
        subprocess.run(['busctl','--user','call','org.kde.KWin','/Effects',
                        'org.kde.kwin.Effects','loadEffect','s',PLUGIN],
                        check=True,capture_output=True,text=True,timeout=5)
        readback=subprocess.run(['busctl','--user','call','org.kde.KWin','/Effects',
                        'org.kde.kwin.Effects','isEffectLoaded','s',PLUGIN],
                        check=True,capture_output=True,text=True,timeout=3)
        loaded=readback.stdout.strip()=='b true'
        return dict(available=loaded, reason='' if loaded else 'KWin did not load the scoped effect')
    except (OSError,subprocess.SubprocessError) as exc:
        return dict(available=False, reason=str(exc))
