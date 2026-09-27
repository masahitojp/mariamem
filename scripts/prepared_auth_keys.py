"""Fixed PUBLIC test-only RSA material; deterministic guest header, never key generation."""
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'guest/test-auth-keypair.json'


def key_material(path=FIXTURE):
    record = json.loads(path.read_text())
    if record.get('version') != 1 or record.get('test_only') is not True:
        raise ValueError('prepared RSA fixture must be explicitly public test-only material')
    result = {}
    for name, label in (('private', 'PRIVATE KEY'), ('public', 'PUBLIC KEY')):
        raw = base64.b64decode(record[name+'_der_base64'], validate=True)
        if not raw or hashlib.sha256(raw).hexdigest() != record[name+'_der_sha256']:
            raise ValueError('prepared RSA fixture hash mismatch: '+name)
        body = base64.b64encode(raw).decode('ascii')
        result[name] = '-----BEGIN '+label+'-----\n'+'\n'.join(body[i:i+64] for i in range(0,len(body),64))+'\n-----END '+label+'-----\n'
    return result


def write_header(source):
    keys = key_material()
    destination = source/'wasm/mariamem_test_auth_keypair.h'
    destination.write_text('/* PUBLIC NON-SECRET RSA-2048 test fixture. Never use for production credentials. */\n'+
                           ''.join('static const char mariamem_test_'+name+'_pem[]= '+json.dumps(value)+';\n' for name,value in keys.items()))
    return 'wasm/mariamem_test_auth_keypair.h'
