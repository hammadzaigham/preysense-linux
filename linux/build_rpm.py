#!/usr/bin/env python3
"""Build an RPM/SRPM from current source, without modifying the host installation."""
import argparse,os,shutil,subprocess,tarfile,tempfile
from pathlib import Path
from version import __version__
def build(output):
    root=Path(__file__).resolve().parents[1]
    if shutil.which('rpmbuild') is None:raise SystemExit('Install rpm-build to create RPM packages.')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='preysense-rpmbuild-') as directory:
        top=Path(directory)
        for name in ('SOURCES','SPECS','BUILD','BUILDROOT','RPMS','SRPMS'):(top/name).mkdir()
        files=set(root.joinpath('linux').glob('*.py'))|set(root.joinpath('linux').glob('*.sh'))|{root/'LICENSE'}
        for pattern in ('linux/assets/*','linux/audio_backend/*','linux/kwin/**/*','linux/packaging/rpm/*','docs/linux/*.md','PreySense.Frontend/Resources/*.png','PreySense.Frontend/Resources/Font.otf','PreySense.Frontend/appicon.svg'):
            files.update(p for p in root.glob(pattern) if p.is_file())
        for name in ('preysense.c','Makefile','dkms.conf','COPYING'):files.add(root/'linux/kernel'/name)
        archive=top/'SOURCES'/f'preysense-{__version__}.tar.gz'
        with tarfile.open(archive,'w:gz') as stream:
            for path in sorted(files):stream.add(path,arcname=f'preysense-{__version__}/'+str(path.relative_to(root)),recursive=False)
        spec=top/'SPECS/preysense.spec';shutil.copyfile(root/'linux/packaging/rpm/preysense.spec',spec)
        subprocess.run(['rpmbuild','-ba','--define',f'_topdir {top}','--define','_build_id_links none',str(spec)],check=True)
        artifacts=list((top/'RPMS').rglob('*.rpm'))+list((top/'SRPMS').glob('*.rpm'))
        for artifact in artifacts:
            target=output/artifact.name;shutil.copy2(artifact,target);print(target)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'dist/rpm'));args=parser.parse_args();build(args.output)
