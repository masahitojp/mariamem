"""Pure, registered guest-input resolution. No preparation or ambient ROOT/LOCK.

The registry is reviewed caller-supplied data. read_bytes reads only a requested
relative fixture/input path; the caller owns storage and symlink policy. This
module performs no filesystem, network, Git or process operations. A successful
resolution proves input identity, not source preparation or release eligibility.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re


class InputError(ValueError):
    """The selected input set is unknown, malformed or inconsistent."""


def _require(condition, message):
    if not condition:
        raise InputError(message)


def _path(value):
    _require(isinstance(value, str) and value and '\\' not in value and ':' not in value
             and '\x00' not in value, 'unsafe path')
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')),
             'unsafe path')
    return value


def _hash(value, length=64):
    _require(isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value),
             'invalid identity')
    return value


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError('invalid JSON constant: ' + value)


def _json(data):
    _require(isinstance(data, bytes), 'reader must return bytes')
    return json.loads(data, object_pairs_hook=_pairs,
                      parse_constant=_invalid_constant)


def _read(reference, read_bytes):
    _require(set(reference) == {'file', 'sha256'}, 'invalid file reference')
    path = _path(reference['file'])
    expected = _hash(reference['sha256'])
    data = read_bytes(path)
    _require(isinstance(data, bytes), 'reader must return bytes')
    _require(_digest(data) == expected, 'file digest mismatch: ' + path)
    return data


def _images(images):
    _require(isinstance(images, dict) and images, 'missing patch images')
    for name, identity in images.items():
        _path(name)
        if identity is not None:
            _hash(identity)


def resolve_inputs(registry_bytes, engine, profile, read_bytes):
    """Return fresh validated input/lock/stage/proof objects for one selection.

    Registry pins descriptor bytes AND semantic output identities/order. Editing
    a descriptor requires a reviewed registry update. Registry is the trust root,
    not a signature scheme. Original byte identities remain in historical records;
    returned JSON objects must not be substituted into old provenance receipts.
    """
    try:
        return _resolve(registry_bytes, engine, profile, read_bytes)
    except InputError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, ValueError, UnicodeError) as exc:
        raise InputError('malformed guest input: ' + str(exc)) from exc


def _resolve(registry_bytes, engine, profile, read_bytes):
    registry = _json(registry_bytes)
    _require(type(registry['schema']) is int and registry['schema'] == 1, 'unknown registry schema')
    _require(isinstance(engine, str) and isinstance(profile, str), 'invalid selection')
    selection = engine + '/' + profile
    _require(selection in registry['selections'], 'unregistered selection')
    entry = registry['selections'][selection]
    descriptor = _json(_read(entry['descriptor'], read_bytes))
    _require(type(descriptor['schema']) is int and descriptor['schema'] in (1, 2), 'unknown descriptor schema')
    _require(descriptor['engine'] == engine and descriptor['profile'] == profile, 'selection mismatch')
    _require(_hash(descriptor['origin'], 40) == _hash(entry['origin'], 40), 'origin mismatch')
    guest = descriptor['guest_input']
    _require(guest['version'] == engine, 'engine mismatch')
    _require(guest.get('prepared_profile', 'legacy-full') == profile, 'profile mismatch')
    _require(profile in ('legacy-full', 'native-text'), 'unknown profile')
    _require(('native_overlay' in guest) == (profile == 'native-text'), 'native route mismatch')
    _hash(guest['source_commit'], 40)
    if descriptor['schema'] == 1:
        _hash(guest['tag_object_sha'], 40)
        _require(guest['source_commit'] != guest['tag_object_sha'], 'source/tag identity conflation')
    else:
        # Explicit preview source provenance; never fabricate an annotated tag.
        proof = descriptor.get('preview_source', {})
        _require(set(proof) == {'kind', 'release', 'source_commit', 'archive_url',
                                'archive_sha256', 'revision_file', 'upstream_ref'},
                 'invalid preview schema')
        _require(proof['kind'] == 'published-preview' and proof['release'] == engine and
                 proof['source_commit'] == guest['source_commit'] and guest['tag_object_sha'] is None,
                 'preview source identity mismatch')
        _require(proof['archive_url'] ==
                 f'https://archive.mariadb.org/mariadb-{engine}/source/mariadb-{engine}.tar.gz',
                 'preview archive origin mismatch')
        _hash(proof['archive_sha256'])
        _require(isinstance(proof['upstream_ref'], str) and
                 proof['upstream_ref'].startswith('refs/heads/preview-'), 'invalid preview reference')
        _path(proof['revision_file'])
    _require(_digest(_encoded(guest)) == _hash(entry['input_sha256']), 'registered input mismatch')

    lock = _json(_read(descriptor['shared_lock'], read_bytes))
    inputs = lock['inputs']
    engine_entry = descriptor['engine_entry']
    position = descriptor['engine_position']
    _require(type(position) is int and 0 <= position <= len(inputs), 'invalid engine position')
    _require(engine_entry['name'] == guest['source_input'], 'engine lock name mismatch')
    _require(engine_entry['revision'] == guest['source_commit'] and
             engine_entry['sha256'] == guest['source_archive_sha256'], 'engine lock identity mismatch')
    inputs.insert(position, engine_entry)
    names = [item['name'] for item in inputs]
    _require(len(set(names)) == len(names), 'duplicate lock input')
    for item in inputs:
        _path(item['file'])
        _hash(item['sha256'])
    recipe = next((x for x in inputs if x['name'] == guest['recipe_input']), None)
    _require(recipe is not None and recipe['revision'] == guest['recipe_source_commit'] and
             recipe['sha256'] == guest['recipe_archive_sha256'], 'recipe identity mismatch')
    _require(_digest(_encoded(lock)) == _hash(entry['lock_sha256']), 'registered lock mismatch')

    stages = descriptor['stages']
    _require(isinstance(stages, list) and stages and all(isinstance(x, str) for x in stages),
             'invalid stages')
    _require(len(set(stages)) == len(stages), 'duplicate stage')
    _require(_digest(_encoded(stages)) == _hash(entry['stages_sha256']), 'registered stage order mismatch')
    groups = list(guest['patches'])
    groups += [guest[k] for k in ('source_overlay', 'observation_overlay', 'native_overlay') if k in guest]
    files = descriptor['files']
    verified = {}
    for name, reference in files.items():
        _path(name)
        verified[name] = _read(reference, read_bytes)
    if descriptor['schema'] == 2:
        revision = verified.get(proof['revision_file'])
        _require(revision == ('#define SOURCE_REVISION "' + guest['source_commit'] + '"\n').encode(),
                 'published preview source revision mismatch')
    patch_names = []
    for patch in groups:
        name = _path(patch['file'])
        patch_names.append(name)
        _require(name in verified, 'missing patch input')
        _require(_digest(verified[name]) == _hash(patch['sha256']), 'patch identity mismatch')
        for key in ('before_sha256', 'after_sha256'):
            _images(patch[key])
        members = re.findall(r'^\+\+\+ b/(.+)$', verified[name].decode(), re.M)
        # A reviewed patch may contain successive sections for the same file.
        # Exact bytes and complete file sets remain mandatory.
        _require(members and set(members) == set(patch['before_sha256']) == set(patch['after_sha256']),
                 'patch file inventory mismatch')
    _require(len(set(patch_names)) == len(patch_names), 'duplicate patch')
    _require('guest/source.patch' in verified, 'missing canonical patch record')
    pin = _json(verified['guest/prepared_source_patch.json'])
    _require(pin['source_commit'] == guest['source_commit'] and
             pin.get('profile', 'legacy-full') == profile, 'prepared proof selection mismatch')
    prepared = [p for p in guest['patches'] if p['file'] == pin['patch_file']]
    _require(len(prepared) == 1 and prepared[0]['sha256'] == pin['patch_sha256'],
             'prepared proof patch mismatch')
    changed = [p for p in pin['files'] if p['before_sha256'] != p['after_sha256']]
    for key in ('before_sha256', 'after_sha256'):
        _require(prepared[0][key] == {p['file']: p[key] for p in changed}, 'prepared proof images mismatch')
    for path, field in (('tests/fixtures/prepared-p2-source-functions.json', 'component_fixture_sha256'),
                        ('tests/fixtures/prepared-param-order-functions.json', 'parameter_fixture_sha256')):
        _require(_digest(verified[path]) == pin[field], 'prepared function proof mismatch')
    result = {'schema': 1, 'selection': selection, 'origin': descriptor['origin'],
            'guest_input': guest, 'effective_lock': lock, 'stages': stages,
            'files': files, 'historical_prepared_pin': pin,
            'descriptor_sha256': entry['descriptor']['sha256'],
            'resolved_sha256': _digest(_encoded({'input': guest, 'lock': lock, 'stages': stages, 'files': files})),
            'scope': 'input identity only; not prepared-source validation or release qualification'}

    if descriptor['schema'] == 2:
        result['preview_source'] = proof
        result['prepared_pin'] = result.pop('historical_prepared_pin')
    return result
