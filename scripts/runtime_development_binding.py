"""Explicit single-guest experiment binding; canonical adapters are never mutated."""
import hashlib
import importlib.util
import json

NAME = 'lexer-prepared-c1'
PROFILE_SHA256 = 'c62401a2712090b696a1fcff57679d427ba57f9d39178bf20376a7177897ef10'


def profile(root, name):
    if name != NAME:
        raise ValueError('unknown development binding')
    path = root/'benchmarks/lexerhost/binding.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PROFILE_SHA256:
        raise ValueError('development binding profile changed')
    value = json.loads(path.read_text())
    for file, expected in value['adapter_sha256'].items():
        if hashlib.sha256((root/'scripts'/file).read_bytes()).hexdigest() != expected:
            raise ValueError('development binding adapter changed: '+file)
    if hashlib.sha256((root/'benchmarks/lexerhost/worker-layout.json').read_bytes()).hexdigest() != value['worker_layout_sha256']:
        raise ValueError('development worker layout changed')
    return value


def adapters(root, name, guest_sha256):
    p = profile(root, name)
    if guest_sha256 != p['guest_sha256']:
        raise ValueError('development binding guest mismatch')
    def load(file):
        spec = importlib.util.spec_from_file_location('development_'+file, root/'scripts'/(file+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    thread, crc = load('runtime_thread_lifetime'), load('runtime_crc32c')
    thread.GUEST_SHA256 = crc.GUEST_SHA256 = guest_sha256
    thread.FUNCTIONS = {k:tuple(v) for k,v in p['thread_functions'].items()}
    crc.BODY_SHA256, crc.TABLE_OFFSET = p['crc_body_sha256'], p['crc_table_offset']
    return thread, crc


def verify_raw(root, name, guest_record, raw_record):
    p = profile(root, name)
    if (guest_record['source_identity']['commit'] != p['source_commit'] or
        guest_record['guest_sha256'] != p['guest_sha256'] or
        raw_record['files_sha256'] != p['raw_files_sha256']):
        raise ValueError('development binding origin/translation mismatch')
    return p
