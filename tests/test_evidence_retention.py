"""Evidence storage guards accept compact records and reject encoded archives."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_public import public_files, check, review_input_references


def test_compact_receipt_and_fixture_remain_publishable(tmp_path):
    for rel in ('docs/reviews/gate/README.md', 'tests/fixtures/contract.json', 'tests/fixtures/sql-source.base64'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}\n')
    assert len(public_files(tmp_path)) == 3


@pytest.mark.parametrize('rel', [
    'docs/reviews/gate/ci.zip.base64',
    'docs/reviews/gate/ci.zip',
    'tests/fixtures/ci.zip.base64',
])
def test_raw_archive_cannot_hide_in_source_tree(tmp_path, rel):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('encoded payload\n')
    with pytest.raises(ValueError, match='generated/binary|encoded CI archive'):
        public_files(tmp_path)


@pytest.mark.parametrize('source', [
    'data = (ROOT / "docs/reviews/contract.json").read_text()',
    'data = (Path("docs") / "reviews" / "contract.json").read_text()',
    'data = open("docs/" + "reviews/contract.json").read()',
    'data = Path("docs", "reviews", "contract.json").read_text()',
    'data = Path(ROOT, "docs", "reviews", "contract.json").read_bytes()',
    'data = Path("./docs/reviews/contract.json").read_text()',
])
def test_new_review_input_is_rejected(tmp_path, source):
    path = tmp_path / 'scripts/new_reader.py'
    path.parent.mkdir()
    path.write_text(source)
    with pytest.raises(ValueError, match='review path in maintained Python input'):
        check(tmp_path)


def test_comment_and_documentation_are_not_executable_dependencies():
    assert review_input_references(
        '"""See docs/reviews/historical.md."""\n'
        '# docs/reviews/old.json\n'
        'data = (ROOT / "tests/fixtures/contract.json").read_text()\n') == []


@pytest.mark.parametrize('source', [
    'REFERENCE = "https://github.com/example/repo/blob/abc/docs/reviews/old.md"',
    'REFERENCE = "https://github.com/example/repo/blob/abc/" + "docs/reviews/old.md"',
    'MESSAGE = "See docs/reviews/old.md for background"',
    'REFERENCE = "docs/reviews-other/contract.json"',
])
def test_historical_references_do_not_create_input_dependencies(tmp_path, source):
    path = tmp_path / 'scripts/reference.py'
    path.parent.mkdir()
    path.write_text(source)
    assert check(tmp_path)['passed']


def test_url_does_not_hide_a_separate_review_read(tmp_path):
    path = tmp_path / 'scripts/reader.py'
    path.parent.mkdir()
    path.write_text(
        'REFERENCE = "https://github.com/example/repo/blob/abc/docs/reviews/old.md"\n'
        'data = Path("docs", "reviews", "contract.json").read_text()\n')
    with pytest.raises(ValueError, match='review path in maintained Python input'):
        check(tmp_path)



def test_review_module_marker_is_not_an_archive_input():
    assert review_input_references('marker = Path("docs/reviews/go.mod")') == []
    assert review_input_references('data = Path("docs/reviews/contract.json").read_text()') == [1]


def test_c_compaction_preserves_build_outcomes_and_source_commits():
    import json
    import hashlib
    import subprocess
    from layout import BENCHMARKS
    root = Path(__file__).resolve().parents[1]
    campaign = BENCHMARKS / 'forkcost/buffer-zero-candidate'
    retention = json.loads((root / campaign / 'retention.json').read_text())
    for row in retention['compacted']:
        raw = subprocess.check_output(['git', '-C', str(root), 'show',
                                      retention['source_commit'] + ':' + (campaign / row['path']).as_posix()])
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        original = json.loads(raw)
        current = json.loads((root / campaign / row['path']).read_text())
        assert set(current) == set(original)
        for key, value in original.items():
            if key in row['fields']:
                if 'commit' in value:
                    assert current[key]['commit'] == value['commit']
            else:
                assert current[key] == value


def test_c_retains_hash_bound_previous_canonical_record():
    import hashlib
    import json
    root = Path(__file__).resolve().parents[1]
    previous = json.loads((root / 'release/generated-go-build.json').read_text())['previous_canonical_evidence']
    assert hashlib.sha256((root / previous['record']).read_bytes()).hexdigest() == previous['record_sha256']


def test_c_retained_manifest_has_no_missing_or_changed_files():
    import hashlib
    import json
    from layout import BENCHMARKS
    root = Path(__file__).resolve().parents[1] / BENCHMARKS / 'forkcost/buffer-zero-candidate'
    for name, digest in json.loads((root / 'SHA256SUMS.json').read_text()).items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
