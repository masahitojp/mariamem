"""Candidate pins describe source before the installation adapter."""
import hashlib
import json
import shutil
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_memfs import apply_mapping
from layout import BENCHMARKS, GENERATED, GENERATED_CODE

def test_candidate_mapping_pin_precedes_installation():
    template=ROOT/BENCHMARKS/'spikes/generated-go-integration/prepared-files.go.txt'
    text=subprocess.check_output(['gofmt'],input=template.read_bytes()).decode()
    pins=json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    assert hashlib.sha256(text.encode()).hexdigest()==pins['candidate_files_sha256']['generated/base/prepared_files.go']
    installed=apply_mapping(text).replace('example.com/mariamem-spike/generated','github.com/masahitojp/mariamem/internal/generatedgo/code')
    installed=subprocess.check_output(['gofmt'],input=installed.encode()).decode()
    assert installed==(ROOT/GENERATED_CODE/'base/prepared_files.go').read_text()


def test_unreviewed_input_manifest_change_rejected(tmp_path):
    import pytest
    from distribution_licenses import verify_generated_attribution
    policy=json.loads((ROOT/'release/attribution-tolerance.json').read_text())
    provenance=json.loads((ROOT/GENERATED/'provenance.json').read_text())
    evidence=json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    (tmp_path/'release').mkdir()
    (tmp_path/GENERATED).mkdir(parents=True)
    (tmp_path/'release/attribution-tolerance.json').write_text(json.dumps(policy))
    for entry in policy['metadata_files'] + policy['generated_file_deltas']:
        relative = GENERATED / entry['path']
        if (ROOT/relative).is_file():
            (tmp_path/relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, tmp_path/relative)
    shutil.copyfile(ROOT/'release/generated-go-inputs.json', tmp_path/'release/generated-go-inputs.json')
    staged = tmp_path/GENERATED/'provenance.json'
    shutil.copyfile(ROOT/GENERATED/'provenance.json', staged)
    assert verify_generated_attribution(tmp_path, evidence) == verify_generated_attribution(ROOT, evidence)

    provenance['input_manifest_sha256'] = '0'*64
    staged.write_text(json.dumps(provenance, indent=2) + '\n')
    error = ('unapproved input manifest' if 'input_manifest_delta' in policy
             else 'generated attribution source changed beyond')
    with pytest.raises(ValueError, match=error):
        verify_generated_attribution(tmp_path, evidence)
