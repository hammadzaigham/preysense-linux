"""Pinned per-user AcerUltraX CLI/daemon setup; no downloaded installer execution."""
import hashlib,io,os,shutil,subprocess,tarfile,tempfile,urllib.request
from pathlib import Path
VERSION='0.1.4'
URL=f'https://github.com/fawaz7/AcerUltraX/releases/download/v{VERSION}/acerultrax-{VERSION}-x86_64-linux.tar.gz'
SHA256='00fdd260c69acec88b878fe31dfeff39da7a061ba19a44a1d3c400f5dcb56df3'
STEREO_DAEMON_SHA256='1877fb1f7c2ba45d1bbf402cd5c01883cb73fde9c7dd8b4f3b0d4e32b586d56a'

def install_stereo_daemon(bindir):
    bundled=Path(__file__).resolve().parent/'audio_backend/acerultrax-daemon'
    if not bundled.is_file() or hashlib.sha256(bundled.read_bytes()).hexdigest()!=STEREO_DAEMON_SHA256:
        raise RuntimeError('Bundled stereo audio backend checksum verification failed')
    daemon=bindir/'acerultrax-daemon'
    if daemon.is_file() and hashlib.sha256(daemon.read_bytes()).hexdigest()==STEREO_DAEMON_SHA256:return False
    with tempfile.NamedTemporaryFile(dir=bindir,delete=False) as target:
        target.write(bundled.read_bytes());temporary=Path(target.name)
    temporary.chmod(0o755);temporary.replace(daemon)
    return True

def setup():
    if os.geteuid()==0:raise SystemExit('Run audio setup as the desktop user, not root')
    bindir=Path.home()/'.local/bin';cli=bindir/'acerultrax-cli';daemon=bindir/'acerultrax-daemon'
    if not cli.is_file() or not daemon.is_file():
        if os.uname().machine!='x86_64':raise SystemExit('Pinned AcerUltraX build supports x86_64 only')
        with urllib.request.urlopen(URL,timeout=60) as response:payload=response.read(100*1024*1024+1)
        if len(payload)>100*1024*1024 or hashlib.sha256(payload).hexdigest()!=SHA256:raise SystemExit('AcerUltraX archive checksum/size verification failed')
        bindir.mkdir(parents=True,exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            for name in ('acerultrax-cli','acerultrax-daemon'):
                members=[m for m in archive.getmembers() if m.isfile() and (m.name.endswith('/bin/'+name) or m.name=='bin/'+name)]
                if len(members)!=1:raise SystemExit('Unexpected AcerUltraX archive layout')
                with archive.extractfile(members[0]) as source,tempfile.NamedTemporaryFile(dir=bindir,delete=False) as target:
                    shutil.copyfileobj(source,target);temporary=Path(target.name)
                temporary.chmod(0o755);temporary.replace(bindir/name)
    changed=install_stereo_daemon(bindir)
    if changed:subprocess.run(['systemctl','--user','try-restart','acerultrax.service'],check=True)
    # A populated imported manifest is retained, never reset during an update.
    manifest=Path.home()/'.local/share/acerultrax/manifest.toml'
    subprocess.run([str(cli),'detect'],check=True)
    if not manifest.is_file():subprocess.run([str(cli),'setup'],check=True)
    subprocess.run([str(cli),'autostart','on'],check=True)
    subprocess.run([str(cli),'status'],check=True)
if __name__=='__main__':setup()
