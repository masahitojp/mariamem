#!/usr/bin/env python3
"""Frozen v0.4 Release CI handoff/guard/reuse; no rebuilding during acceptance."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from common import ROOT,digest
from check_public import public_files
from ci_release_reuse import GitHub, safe_name
from generated_release import (CONTRACT,PLATFORMS,checkout,guard,check_aggregate,package_source,
                               require,read,write,stage,verify_build,verify_source,verify_wheel,version)

EVIDENCE={'build/release/generated-acceptance.json','build/release/generated-acceptance.log',
          'tests/evidence/alpha.json','build/release/ci-ready.json','build/release/ci-guard.log',
          'build/release/runtime-validation.json'}


def handoff_paths(root,platform):
    source=read(root/'build/release/generated-source.json')
    wheel,_=verify_wheel(root,platform)
    paths=['build/generated-release','build/release/generated-source.json',
            'build/release/'+source['file'],wheel.relative_to(root).as_posix(),
            'tests/evidence/alpha-wheel.json']
    from runtime_validation import read_intent, verify_frozen, PROOF
    if read_intent(root):
        verify_frozen(root,read(root/'tests/evidence/alpha-wheel.json')['source_commit'])
        paths.append(PROOF)
    return paths


def freeze(root,commit,platform,output):
    checkout(root,commit); verify_build(root,commit); verify_source(root,commit); verify_wheel(root,platform,commit)
    require(not output.exists(),'refuse replacing frozen handoff')
    with tarfile.open(output,'w') as tar:
        for name in handoff_paths(root,platform): tar.add(root/name,arcname=name)
    output.with_suffix('.sha256').write_text(digest(output)+'\n')


def allowed(name,directory=False):
    name=safe_name(name)
    exact={'build/generated-release/guest.json','build/generated-release/regeneration.json',
           'build/generated-release/mariamem.wasm','build/generated-release/link.txt',
           'build/generated-release/flags.make','build/generated-release/CMakeCache.txt',
           'build/release/generated-source.json','tests/evidence/alpha-wheel.json',
           'build/release/runtime-validation.json'}
    acceptable=name in exact or (name.startswith('build/release/mariamem-') and name.endswith('-corresponding-source.tar.gz') and len(Path(name).parts)==3)
    acceptable=acceptable or (name.startswith('build/dist/mariamem-') and name.endswith('.whl') and len(Path(name).parts)==3)
    if directory: acceptable=name in {'build','build/generated-release','build/release','build/dist','tests','tests/evidence'}
    require(acceptable,'unexpected generated-Go handoff path: '+name)
    return name


def restore_handoff(archive,expected,root):
    require(digest(archive)==expected,'handoff SHA256 mismatch')
    with tarfile.open(archive,'r:') as tar:
        members=tar.getmembers(); seen=set()
        for m in members:
            name=allowed(m.name,m.isdir()); require(name not in seen,'duplicate handoff entry'); seen.add(name)
            require(m.isfile() or m.isdir(),'link/special handoff entry')
            target=root/name
            require(not target.is_symlink() and not any(p.is_symlink() for p in target.parents),'symlink destination')
            if m.isfile(): require(not target.exists(),'refuse overwriting frozen candidate')
        for m in members:
            target=root/safe_name(m.name)
            if m.isdir(): target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(m) as src,target.open('wb') as dst: shutil.copyfileobj(src,dst)
                target.chmod(m.mode&0o777)


def unzip(path,destination,candidate=False):
    names={'candidate-handoff.tar','candidate-handoff.sha256'} if candidate else EVIDENCE
    with zipfile.ZipFile(path) as archive:
        seen=set()
        for member in archive.infolist():
            name=safe_name(member.filename.rstrip('/')); mode=member.external_attr>>16
            require(name not in seen,'duplicate ZIP entry'); seen.add(name)
            require(not stat.S_ISLNK(mode) and stat.S_IFMT(mode) in (0,stat.S_IFREG,stat.S_IFDIR),'special ZIP entry')
            if member.is_dir(): require(any(n.startswith(name+'/') for n in names),'unexpected ZIP directory')
            else: require(name in names,'unexpected ZIP evidence entry: '+name)
        for member in archive.infolist():
            if member.is_dir(): continue
            name=safe_name(member.filename)
            if not candidate and name not in {'build/release/generated-acceptance.json','tests/evidence/alpha.json'}: continue
            target=destination/name
            require(not target.exists() and not any(p.is_symlink() for p in [target,*target.parents]),'refuse overwriting evidence/symlink')
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(member) as src,target.open('wb') as dst: shutil.copyfileobj(src,dst)


def restore_platform(root,commit,platform,mode,archive=None,sha=None,candidate_run=None,evidence_run=None):
    checkout(root,commit)
    with tempfile.TemporaryDirectory(prefix='mariamem-v04-reuse-') as temporary:
        work=Path(temporary).resolve()
        api=GitHub(os.environ.get('GITHUB_REPOSITORY','masahitojp/mariamem'),os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN'))
        if mode!='full':
            require(candidate_run and int(candidate_run)>0,'original candidate run required; no rebuild fallback')
            api.artifact(candidate_run,'release-candidate-'+platform+'-'+commit,commit,work/'candidate.zip')
            unzip(work/'candidate.zip',work,candidate=True)
            archive=work/'candidate-handoff.tar'; sha=(work/'candidate-handoff.sha256').read_text().strip()
        require(archive is not None and sha is not None,'missing immutable handoff/hash')
        restore_handoff(archive,sha,root)
        verify_build(root,commit); verify_source(root,commit); verify_wheel(root,platform,commit)
        if mode=='guard-only':
            require(evidence_run and int(evidence_run)>0,'exact acceptance evidence run required')
            api.artifact(evidence_run,'release-evidence-'+platform+'-'+commit,commit,work/'evidence.zip')
            unzip(work/'evidence.zip',root)
            guard(root,commit,platform)


def restore_all(root,commit,candidate_run,evidence_run):
    checkout(root,commit)
    for platform in PLATFORMS:
        project=root/'build/platforms'/platform
        require(not project.exists(),'refuse replacing platform evidence')
        for source in public_files(root):
            destination=project/source.relative_to(root); destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
        restore_platform(project,commit,platform,'guard-only',candidate_run=candidate_run,evidence_run=evidence_run)


def public_smoke(root,commit,platform,publication,repository,smoke_program=None,recovery=None):
    from generated_release_acceptance import accept
    from published_assets import verify_downloads, verify_publication
    from generated_release import expected_names
    record=read(publication); require(record['status']=='PUBLISHED' and record['source_commit']==commit,'publication not accepted')
    require(set(record['assets'])==expected_names(version(root)['PYTHON_VERSION'])|{'SHA256SUMS'},'published asset contract differs')
    with tempfile.TemporaryDirectory(prefix='mariamem-v04-public-') as temporary:
        work=Path(temporary).resolve()
        subprocess.run(['gh','release','download',record['git_tag'],'--repo',repository,'--dir',work],check=True)
        verify_downloads(work,record['assets'])
        # The existing frozen wheel metadata is reconstructed from accepted
        # release provenance, never from a new build of a public artifact.
        provenance=read(work/f"mariamem-{record['python_version']}-provenance.json")
        verify_publication(record,provenance,commit,version(root),repository)
        wheel_record=provenance['platforms'][platform]['wheel_record']
        destination=root/wheel_record['wheel']; destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(work/destination.name,destination)
        write(root/'tests/evidence/alpha-wheel.json',wheel_record)
        output=root/'build/release'/('ci-public-smoke-recovery.json' if recovery else 'ci-public-smoke.json')
        accept(root,commit,platform,output,mode='published',publication=record,
               smoke_program=smoke_program,recovery=recovery)


def verify_smoke_repair(root,commit,repair):
    """Only a pinned consumer program can differ; accepted checkout stays intact."""
    import re
    require(re.fullmatch('[0-9a-f]{40}',repair or '') is not None,'full smoke repair SHA required')
    checkout(root,commit)
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
    require(git('cat-file','-t',repair)=='commit','smoke repair must be a commit')
    paths=git('diff','--name-only','--no-renames',commit,repair).splitlines()
    require(paths==['scripts/guest_smoke/main.go'],'repair must change only the Go smoke program')
    require(git('ls-tree',repair,'scripts/guest_smoke/main.go').startswith('100644 blob '),
            'repair program must be a regular file')
    return subprocess.check_output(['git','-C',str(root),'show',repair+':scripts/guest_smoke/main.go'])


def authenticated_publication(api,run,commit,destination):
    """A failed overall smoke run can still have a successful publication job."""
    from ci_release_reuse import WORKFLOW
    require(run and int(run)>0,'original publication run required')
    info=api.json(f'/actions/runs/{run}')
    require(info.get('path','').split('@',1)[0]==WORKFLOW
            and info.get('head_sha')==commit and info.get('status')=='completed'
            and info.get('event')=='workflow_dispatch','original publication run identity differs')
    jobs=[]; page=1
    while True:
        batch=api.json(f'/actions/runs/{run}/jobs?filter=all&per_page=100&page={page}')['jobs']
        jobs.extend(batch)
        if len(batch)<100: break
        page+=1
    require(any(j.get('name')=='publication' and j.get('conclusion')=='success' for j in jobs),
            'original publication job did not succeed')
    proof=api.artifact(run,'release-publication-'+commit,commit,destination)
    with zipfile.ZipFile(destination) as archive:
        require(archive.namelist()==['ci-publication.json'],'unexpected publication archive inventory')
        member=archive.infolist()[0]
        require(stat.S_IFMT(member.external_attr>>16) in (0,stat.S_IFREG)
                and member.file_size<4*1024*1024,'unsafe publication receipt')
        record=json.loads(archive.read(member))
    require(record.get('status')=='PUBLISHED' and record.get('source_commit')==commit,
            'publication receipt source/status differs')
    return record,proof


def recover_public_smoke(root,commit,platform,repository,run,repair):
    from native_target import UBUNTU
    require(platform==UBUNTU,'this recovery targets the remaining Ubuntu smoke')
    program=verify_smoke_repair(root,commit,repair)
    with tempfile.TemporaryDirectory(prefix='mariamem-public-recovery-') as temporary:
        work=Path(temporary).resolve()
        api=GitHub(repository,os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN'))
        record,proof=authenticated_publication(api,run,commit,work/'publication.zip')
        publication=work/'ci-publication.json'; write(publication,record)
        fixed=work/'main.go'; fixed.write_bytes(program)
        tools=Path(__file__).resolve().parents[1]
        tooling_sha=subprocess.check_output(['git','-C',str(tools),'rev-parse','HEAD'],text=True).strip()
        checkout(tools,tooling_sha)
        recovery={'publication':proof,'published_source_commit':commit,
                  'smoke_source_commit':repair,'smoke_program_sha256':digest(fixed),
                  'tooling_source_commit':tooling_sha,'publication_repeated':False,
                  'tooling_files_sha256':{p:digest(tools/p) for p in (
                      'scripts/release_generated_ci.py','scripts/generated_release_acceptance.py',
                      'scripts/published_assets.py','scripts/consumer_acceptance.py',
                      'scripts/ci_release_reuse.py')}}
        public_smoke(root,commit,platform,publication,repository,fixed,recovery)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('source','freeze','restore-platform','restore','guard','public-smoke','recover-public-smoke'))
    p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--candidate-sha',required=True)
    p.add_argument('--platform',choices=PLATFORMS); p.add_argument('--output',type=Path)
    p.add_argument('--mode',choices=('full','acceptance-only','guard-only'),default='full')
    p.add_argument('--handoff',type=Path); p.add_argument('--handoff-sha256')
    p.add_argument('--candidate-run',type=int); p.add_argument('--evidence-run',type=int)
    p.add_argument('--publication',type=Path); p.add_argument('--repository')
    p.add_argument('--smoke-ref')
    a=p.parse_args(); root=a.root.resolve()
    try:
        if a.command=='source': package_source(root,a.candidate_sha)
        elif a.command=='freeze':
            require(a.platform and a.output,'platform/output required'); freeze(root,a.candidate_sha,a.platform,a.output)
        elif a.command=='restore-platform':
            require(a.platform,'platform required'); restore_platform(root,a.candidate_sha,a.platform,a.mode,a.handoff,a.handoff_sha256,a.candidate_run,a.evidence_run)
        elif a.command=='restore': restore_all(root,a.candidate_sha,a.candidate_run,a.evidence_run)
        elif a.command=='public-smoke': public_smoke(root,a.candidate_sha,a.platform,a.publication,a.repository)
        elif a.command=='recover-public-smoke':
            recover_public_smoke(root,a.candidate_sha,a.platform,a.repository,a.candidate_run,a.smoke_ref)
        else:
            result=guard(root,a.candidate_sha,a.platform) if a.platform else check_aggregate(root,a.candidate_sha)
            if a.platform: write(root/'build/release/ci-ready.json',result)
            else: stage(root,result)
            print(json.dumps(result,indent=2))
    except Exception as error:
        if a.command=='guard':
            write(root/'build/release/ci-ready.json',{'version':3,'contract':CONTRACT,
                  'result':'NOT READY','source_commit':a.candidate_sha,'error':str(error)})
        print('Release candidate: NOT READY\n- '+str(error)); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
