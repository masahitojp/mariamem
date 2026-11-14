"""Generated-Go notices plus immutable historical/reference attribution."""
from layout import GENERATED
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
        raise ValueError('license evidence identity differs; inspect scripts/update_evidence_records.py --check')
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


def _sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _relative_file(value):
    return (isinstance(value, str) and value and '\\' not in value and
            not Path(value).is_absolute() and
            all(part not in ('', '.', '..') for part in value.split('/')))


def attribution_tolerance(root):
    """Explicit policy; changes require review, never automatic ledger updates."""
    value = json.loads((Path(root)/'release/attribution-tolerance.json').read_text())
    if (not isinstance(value, dict) or
            set(value) != {'version', 'metadata_files', 'generated_file_deltas'} or
            type(value['version']) is not int or value['version'] != 1):
        raise ValueError('unknown attribution tolerance contract')
    paths = set()
    for group in ('metadata_files', 'generated_file_deltas'):
        if not isinstance(value[group], list):
            raise ValueError('invalid attribution tolerance entries')
        for row in value[group]:
            fields = {'path', 'reason', 'approval', 'before'}
            if group == 'generated_file_deltas':
                fields.add('after')
            if isinstance(row, dict) and group == 'metadata_files' and 'audit_field' in row:
                fields.add('audit_field')
                if not isinstance(row['audit_field'], str) or not row['audit_field'].strip():
                    raise ValueError('invalid attribution audit field')
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError('invalid attribution tolerance entry')
            name = row['path']
            if (not _relative_file(name) or name == 'provenance.json' or name in paths or
                    any(not isinstance(row[k], str) or not row[k].strip()
                        for k in ('reason', 'approval')) or
                    (row['before'] is not None and not _sha256(row['before']))):
                raise ValueError('invalid attribution tolerance entry')
            if group == 'metadata_files':
                if not name.endswith('.json'):
                    raise ValueError('invalid attribution metadata path')
            elif (row['before'] == row['after'] or
                  (row['after'] is not None and not _sha256(row['after']))):
                raise ValueError('invalid generated attribution delta')
            paths.add(name)
    return value


def verify_generated_attribution(root, evidence):
    """Reconstruct the pinned audit using explicitly reviewed file deltas.

    Metadata entries specify their audited hash (None means absent at audit).
    Source deltas require exact before/after hashes. Guest and input identities
    remain covered by the original audit digest. Historical host facts remain
    historical, even when source continuity has been reviewed.
    """
    root = Path(root)
    policy = attribution_tolerance(root)
    for row in policy['metadata_files']:
        field = row.get('audit_field')
        if field in evidence and evidence[field] != row['before']:
            raise ValueError('generated attribution source changed beyond image metadata: audit binding differs')
    path = root/(GENERATED / 'provenance.json')
    expected = evidence['generated_provenance_sha256']
    if digest(path) == expected:
        return 'exact'
    record = json.loads(path.read_text())
    files = record['files_sha256']
    source_changed = False
    for group in ('generated_file_deltas', 'metadata_files'):
        for row in policy[group]:
            name = row['path']
            current = files.get(name)
            if name in files and not _sha256(current):
                raise ValueError('invalid generated attribution hash: '+name)
            if current == row['before']:
                continue
            if group == 'generated_file_deltas':
                if current != row['after']:
                    raise ValueError('unapproved generated attribution delta: '+name)
                source_changed = True
            elif current is None:
                raise ValueError('generated attribution metadata missing: '+name)
            target = root/GENERATED/name
            if current is not None and digest(target) != current:
                raise ValueError('generated attribution metadata mismatch: '+name)
            if current is None and target.exists():
                raise ValueError('deleted generated attribution file still exists: '+name)
            if row['before'] is None:
                files.pop(name, None)
            else:
                files[name] = row['before']
    # First retain the recorded order. Renames may require restoring the
    # generator's sorted file map; either form must match the exact audit hash.
    original = (json.dumps(record, indent=2)+'\n').encode()
    if hashlib.sha256(original).hexdigest() != expected:
        record['files_sha256'] = dict(sorted(files.items()))
        original = (json.dumps(record, indent=2)+'\n').encode()
    if hashlib.sha256(original).hexdigest() != expected:
        raise ValueError('generated attribution source changed beyond image metadata or reviewed deltas')
    return ('reviewed-generated-source-delta' if source_changed else
            'unchanged-generated-code; image-metadata-only')
