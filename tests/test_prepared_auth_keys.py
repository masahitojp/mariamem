"""Fail closed on missing/incorrect causal RSA branch evidence."""
from pathlib import Path
import sys
import json
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks'))
from prepared_auth_keys import verify_branches
from prepared_auth_keys import run


@pytest.mark.parametrize('condition,generated', [('control', True), ('existing-keys', False)])
def test_branch_evidence(condition, generated):
    events = {'auth_load_begin': {}, 'auth_load_complete': {}}
    if generated:
        events.update(auth_generate_begin={}, auth_generate_complete={})
    with patch('prepared_auth_keys.records', return_value=[({}, {}, {})]), patch('prepared_auth_keys.validate', return_value=events):
        assert verify_branches({}, condition) == 1
        with pytest.raises(ValueError, match='incorrect RSA generation'):
            verify_branches({}, 'existing-keys' if generated else 'control')
        events['auth_load_failed'] = {}
        with pytest.raises(ValueError, match='load did not succeed'):
            verify_branches({}, condition)


def test_missing_records_rejected():
    with patch('prepared_auth_keys.records', return_value=[]):
        with pytest.raises(ValueError, match='missing RSA branch'):
            verify_branches({}, 'control')


def test_patch_preserves_plugin_and_generation_predicate():
    text = (ROOT/'guest/experimental.patch').read_text()
    assert 'MYSQL_SYSVAR_NAME(public_key_path).def_val' in text
    assert 'auth_generate_complete' in text and 'auth_load_complete' in text
    assert 'auto-generate-rsa-keys=0' not in text
    assert '--caching-sha2-password-private-key-path=/auth-keys/private.pem' in text
    assert '--caching-sha2-password-public-key-path=/auth-keys/public.pem' in text
    assert '-    ssl_genkeys();' in text and '+    int result= ssl_genkeys();' in text


def test_interleaved_runner_uses_one_key_pair_and_same_settings(tmp_path):
    native = tmp_path/'native'
    native.mkdir()
    (native/'provenance.json').write_text('{}')
    calls = []

    def command(args, **kwargs):
        if args[0] == 'openssl' and '-out' in args:
            Path(args[args.index('-out')+1]).write_text('public test material')
        if '--json' in args:
            calls.append((args, kwargs['env'].get('MARIAMEM_EXPERIMENT_AUTH_KEYS_DIR')))
            Path(args[args.index('--json')+1]).write_text(json.dumps({'samples': []}))

    with patch('prepared_auth_keys.subprocess.run', side_effect=command), \
         patch('prepared_auth_keys.subprocess.check_output', return_value='a'*40), \
         patch('prepared_auth_keys.platform.platform', return_value='test-platform'), \
         patch('prepared_auth_keys.verify_branches', return_value=1) as branch, \
         patch('prepared_auth_keys.summarize', return_value=[]), \
         patch('prepared_auth_keys.summarize_latency', return_value=[]):
        run(native, tmp_path/'results', pairs=2, warmup=0)
    assert [bool(keys) for _, keys in calls] == [False, True, True, False]
    assert calls[1][1] == calls[2][1]
    assert not Path(calls[1][1]).exists()  # private material is discarded
    assert branch.call_count == 4
    for args, _ in calls:
        assert args[args.index('--workers')+1] == '1,4,8'
        assert args[args.index('--rows')+1] == '1000'
        assert '--init-diagnostics' in args and '--memory-diagnostics' in args
    assert json.loads((tmp_path/'results/summary.json').read_text())['pairs'] == 2
