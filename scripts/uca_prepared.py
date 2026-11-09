"""Pinned prepared UCA source input. No runtime decoder or public API."""
import uca_input
from pathlib import Path
from common import digest

BUNDLE = 'benchmarks/ucapreparedinput'
HEADER = 'strings/mariamem_uca_prepared.h'
VERIFY_ENV = 'MARIAMEM_UCA_VERIFY_INTERNAL'


def prepare(root, source):
    """Validate pristine MariaDB inputs before canonical patching; create once."""
    root, source = Path(root), Path(source)
    bundle = root/BUNDLE
    header, check = uca_input.validate(bundle, root, source)
    target = source/HEADER
    with target.open('xb') as output:
        output.write(header)
    return provenance(root, check)


def provenance(root, check):
    bundle = root/BUNDLE
    names = ('input.json', 'level0.u16le.json', 'level1.u16le.json', 'level2.u16le.json')
    return {'contract': 'prepared-uca1400-v1', 'input_files_sha256':
            {BUNDLE+'/'+name: digest(bundle/name) for name in names},
            'source_check': 'PRISTINE_SOURCE_HASHES_PASS', 'header': HEADER,
            'header_sha256': check['header_sha256'], 'numeric_bytes': check['numeric_bytes'],
            'verification_env': VERIFY_ENV}


def verify_record(root, record):
    """Check build attestation against current inputs; never claim a source replay."""
    root = Path(root)
    _, check = uca_input.validate(root/BUNDLE, root)
    if record != provenance(root, check):
        raise ValueError('prepared UCA source-input provenance differs')
