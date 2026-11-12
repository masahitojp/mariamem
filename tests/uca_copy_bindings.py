"""Exact experimental binding for the single Issue154 UNQUALIFIED guest.

Loaded only by the experiment runner. Canonical adapters/files remain unchanged.
No caller-supplied guest/hash/offset or approximate matching is accepted.
"""
import hashlib
import importlib.util
from pathlib import Path

ORIGIN = 'f43257225e1fd65c58ea8f5d7b220c3a509c203b'
GUEST = '332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22'
CANONICAL = 'a64b581154d7d1ca2ca8aae9a552c9433f7f1354b7c7f5a36d600b62a32d2c18'
FUNCTIONS = {
    'code/p3/p3_pure.go': ('Fn153', '0b91dbdbb97dcfe0916ecdc8379769d078e33e3ecf5a3ed85ef0da8b5fe8b9b0'),
    'code/p5/p5_pure.go': ('Fn214', '7c7d83da40e4ed0b7a8ff0f910ffec1a7cbbde21de90e12a2e12b314777ea4a8'),
    'code/p8/p8_pure.go': ('Fn131', 'e31e88a8637fb60e5f197014ae2c4dd0afe2fcd05c6f850c13d24ff0b0810932'),
}
CRC_BODY = '2569b9f4e7022921787050ec11e7fae5b14382416adc732fae562c8f6aca236e'
CRC_OFFSET = 7930560
# Adapter logic itself is immutable. Filled from the inspected origin commit.
ADAPTERS = {'runtime_thread_lifetime': 'd8e3e62050964eafc030d497b26b17182e2e34255ce9a132b304cc16f315240d', 'runtime_crc32c': '724db7b4964ecdf880a2d84ffbcf0f6cdd09fb294af622854122e8c09edf4d9f'}


def load(origin):
    modules = {}
    for name, expected in ADAPTERS.items():
        path = Path(origin) / 'scripts' / (name + '.py')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('unreviewed adapter implementation: ' + name)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.GUEST_SHA256 != CANONICAL:
            raise ValueError('canonical guest binding changed')
        module.GUEST_SHA256 = GUEST
        modules[name] = module
    modules['runtime_thread_lifetime'].FUNCTIONS = dict(FUNCTIONS)
    modules['runtime_crc32c'].BODY_SHA256 = CRC_BODY
    modules['runtime_crc32c'].TABLE_OFFSET = CRC_OFFSET
    return modules


CRC_TEST_SOURCE_SHA256 = '69ac801890c4eec0bd61b9898262f45f33773f0be6f177b7451a49ffdeb01ed4'
CRC_TEST_RELOCATIONS = {
    'copy(mem[15569536:], table)': 'copy(mem[16319168:], table)',
    'm.Memory[26865072:]': 'm.Memory[27614704:]',
}


def crc_test_source(text):
    """Rebind only fixture setup addresses; preserve every test oracle byte."""
    if hashlib.sha256(text.encode()).hexdigest() != CRC_TEST_SOURCE_SHA256:
        raise ValueError('unreviewed original CRC test fixture')
    for before, after in CRC_TEST_RELOCATIONS.items():
        if text.count(before) != 1 or after in text:
            raise ValueError('CRC test fixture relocation anchor changed')
        text = text.replace(before, after, 1)
    return text
