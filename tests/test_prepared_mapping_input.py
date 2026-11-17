"""Candidate pins describe source before the installation adapter."""
import hashlib
import json
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
    provenance['input_manifest_sha256']='0'*64
    (tmp_path/GENERATED/'provenance.json').write_text(json.dumps(provenance))
    with pytest.raises(ValueError,match='unapproved input manifest'):
        verify_generated_attribution(tmp_path,evidence)
