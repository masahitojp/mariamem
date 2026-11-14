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
    verify_generated_attribution(root, json.loads((root/'release/generated-license-evidence.json').read_text()))
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


def verify_generated_attribution(root, evidence):
    """Preserve the historical audit; accept only reversible OS-glue adapters."""
    root = Path(root)
    path = root / 'internal/generatedgo/provenance.json'
    expected = evidence['generated_provenance_sha256']
    current = json.loads(path.read_text())
    for name, checksum in current['files_sha256'].items():
        if digest(root / 'internal/generatedgo' / name) != checksum:
            raise ValueError('generated source differs from provenance: ' + name)
    if digest(path) == expected:
        return 'exact'
    continuity = evidence.get('os_glue_source_continuity', {})
    changes = {
        'code/base/base.go': (
            ('func mapOSError(err error) int32 {\n\tif err == nil {',
             'func mapOSError(err error) int32 {\n\terr = normalizeNativeError(err)\n\tif err == nil {'),
            ('if _, err := op.f.Write(nil); err != nil {',
             'if err := nativeFileWriteProbe(op.f); err != nil {'),
        ),
        'main.go': (
            ('\t"fmt"\n', '\t"fmt"\n\t"github.com/masahitojp/mariamem/internal/entropyfs"\n'),
            ('return os.Open("/" + strings.TrimPrefix(name, "/"))',
             'return entropyfs.Open("/" + strings.TrimPrefix(name, "/"))'),
            ('return os.Stat("/" + strings.TrimPrefix(name, "/"))',
             'return entropyfs.Stat("/" + strings.TrimPrefix(name, "/"))'),
        ),
        'code/base/prepared_files.go': (
            ('\n\t"syscall"', ''),
            ('syscall.Mmap(int(f.Fd()), 0, int(st.Size()), syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE)',
             'mapPreparedMemory(int(f.Fd()), int(st.Size()), false)'),
            ('syscall.Munmap(data)', 'unmapPreparedMemory(data)'),
        ),
    }
    before = continuity.get('previous_file_sha256', {})
    if set(before) != set(changes):
        raise ValueError('OS glue attribution requires the exact three-file boundary')
    record = json.loads(path.read_text())
    for name, edits in changes.items():
        source = root / 'internal/generatedgo' / name
        data = source.read_text()
        if digest(source) != record['files_sha256'][name]:
            raise ValueError('OS glue source differs from provenance: ' + name)
        # Invert only the reviewed adapter. Any other byte change fails the
        # historical preimage hash, including changes to MariaDB function bodies.
        for old, new in reversed(edits):
            if not new:  # Reinsert the removed import in its original location.
                anchor = '\n\t"path/filepath"'
                if data.count(anchor) != 1:
                    raise ValueError('prepared mapping import preimage changed')
                data = data.replace(anchor, anchor + old, 1)
            else:
                if data.count(new) != 1:
                    raise ValueError('OS glue adapter preimage changed: ' + name)
                data = data.replace(new, old, 1)
        if hashlib.sha256(data.encode()).hexdigest() != before[name]:
            raise ValueError('generated source changed beyond OS glue: ' + name)
        record['files_sha256'][name] = before[name]
    restored = (json.dumps(record, indent=2) + '\n').encode()
    if hashlib.sha256(restored).hexdigest() != expected:
        raise ValueError('generated attribution changed beyond OS glue provenance')
    return 'os-glue-continuity'
