"""Generated-Go notices plus immutable historical/reference attribution."""
import json
from pathlib import Path
import hashlib
import tarfile
import zipfile
from common import digest


def inventory(root):
    root = Path(root)
    value = json.loads((root/'release/distribution-licenses.json').read_text())
    if value['version'] != 1 or value['contract'] != 'generated-go-v1':
        raise ValueError('unknown license inventory contract')
    normal, legacy = value['distributed_notices'], value['legacy_notices']
    if set(normal) & set(legacy):
        raise ValueError('overlapping license inventory')
    actual = {p.name for p in (root/'licenses').iterdir() if p.is_file()}
    if actual != set(normal) | set(legacy):
        raise ValueError('unclassified/missing license file')
    for name, checksum in {**normal, **legacy}.items():
        if Path(name).name != name or digest(root/'licenses'/name) != checksum:
            raise ValueError('license bytes differ: '+name)
    classes = {'DISTRIBUTED / DERIVED', 'BUILD-ONLY', 'LEGACY-ONLY', 'UNUSED'}
    if not set(value['components'].values()) <= classes:
        raise ValueError('unknown component classification')
    if digest(root/'release/generated-license-evidence.json') != value['evidence_sha256']:
        raise ValueError('license evidence identity differs')
    return value


def paths(root, *, legacy=False):
    root = Path(root)
    value = inventory(root)
    names = set(value['distributed_notices'])
    if legacy:
        names |= set(value['legacy_notices'])
    return [root/n for n in ('LICENSE', 'NOTICE', 'THIRD_PARTY_LICENSES')] + [
        root/'licenses'/n for n in sorted(names)]


def source_inputs(root, lock):
    excluded = inventory(root)['legacy_source_inputs']
    if excluded != ['wasmer-source']:
        raise ValueError('unexpected corresponding-source exclusion')
    return [entry for entry in lock['inputs']
            if entry.get('kind') != 'runtime-binary' and entry['name'] not in excluded]


def verify_upstream_notices(root, lock, downloads=None):
    root=Path(root); downloads=downloads or root/'build/downloads'
    value=inventory(root); groups={}
    for name, origin in value['upstream_notice_files'].items():
        groups.setdefault(origin['input'],{})[origin['path']]=name
    entries={e['name']:e for e in source_inputs(root,lock)}
    for source,wanted in groups.items():
        entry=entries[source]; archive=downloads/entry['file']; found={}
        if digest(archive)!=entry['sha256']: raise ValueError('upstream archive differs: '+source)
        def check(member,data):
            relative=member.split('/',1)[-1]
            if relative in wanted:
                if relative in found: raise ValueError('duplicate upstream notice')
                found[relative]=hashlib.sha256(data).hexdigest()
        if archive.suffix=='.zip':
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    if name.split('/',1)[-1] in wanted: check(name,z.read(name))
        else:
            with tarfile.open(archive,'r|gz') as tar:
                for member in tar:
                    if member.isfile() and member.name.split('/',1)[-1] in wanted:
                        check(member.name,tar.extractfile(member).read())
                    tar.members.clear()
        if set(found)!=set(wanted): raise ValueError('missing upstream notice: '+source)
        for relative,name in wanted.items():
            if found[relative]!=value['distributed_notices'][name]:
                raise ValueError('upstream notice bytes differ: '+name)
    return True
