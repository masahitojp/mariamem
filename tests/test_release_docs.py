"""Current usage docs must follow the candidate version, not historical releases."""
from pathlib import Path
import shutil
import re
import runpy
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_version import DOCS, check_release_docs
from check_ci_release import check_candidate
from common import ROOT
from release_version import GIT_TAG, PYTHON_VERSION


@pytest.fixture
def candidate(tmp_path):
    for name in (*DOCS, 'python/mariamem/_version.py', 'release/inputs.lock.json'):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_current_release_docs_match(candidate):
    assert check_release_docs(candidate)['tag'] == GIT_TAG


@pytest.mark.parametrize('old,new,label', [
    (f'Release are at `{GIT_TAG}`', 'Release are at `v0.1.0-alpha.2`', 'current tag text'),
    (f'distribution version is `{PYTHON_VERSION}`', 'distribution version is `0.1.0a2`', 'current Python text'),
    (f'mariamem@{GIT_TAG}', 'mariamem@v0.1.0-alpha.2', 'go get'),
    (f'gh release download {GIT_TAG}', 'gh release download v0.1.0-alpha.2', 'gh release download'),
    (f'mariamem-{PYTHON_VERSION}-py3-none-', 'mariamem-0.1.0a2-py3-none-', 'wheel filename'),
])
def test_stale_readme_release_forms_fail(candidate, old, new, label):
    path = candidate / 'README.md'
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    with pytest.raises(ValueError, match=label):
        check_release_docs(candidate)


def test_next_prerelease_with_stale_examples_blocks_guard(candidate):
    source = candidate / 'python/mariamem/_version.py'
    components = runpy.run_path(str(source))
    source.write_text(re.sub(r'SERIAL = \d+', f'SERIAL = {components["SERIAL"] + 1}', source.read_text()))
    expected = runpy.run_path(str(source))['GIT_TAG']
    with pytest.raises(ValueError, match=re.escape('expected ' + expected)):
        check_release_docs(candidate)
    # Guard rejects documentation before considering any artifact/evidence.
    with pytest.raises(ValueError, match=re.escape('expected ' + expected)):
        check_candidate('a' * 40, candidate / 'acceptance.json', root=candidate)


def test_historical_records_are_not_rewritten_or_checked(candidate):
    (candidate / 'release/NOTES.md').write_text('Historical alpha.2: v0.1.0-alpha.2 / 0.1.0a2')
    check_release_docs(candidate)


def test_current_examples_cannot_be_replaced_with_placeholders(candidate):
    path = candidate / 'README.md'
    path.write_text(path.read_text().replace(f'mariamem@{GIT_TAG}', 'mariamem@<published-tag>'))
    with pytest.raises(ValueError, match='missing release-facing go get'):
        check_release_docs(candidate)


def test_next_prerelease_docs_can_be_updated_without_checker_changes(candidate):
    source = candidate / 'python/mariamem/_version.py'
    before = runpy.run_path(str(source))
    source.write_text(re.sub(r'SERIAL = \d+', f'SERIAL = {before["SERIAL"] + 1}', source.read_text()))
    after = runpy.run_path(str(source))
    for name in DOCS:
        path = candidate / name
        path.write_text(path.read_text().replace(before['GIT_TAG'], after['GIT_TAG'])
                        .replace(before['PYTHON_VERSION'], after['PYTHON_VERSION']))
    assert check_release_docs(candidate)['tag'] == after['GIT_TAG']


def test_plain_current_version_text_is_checked(candidate):
    path = candidate / 'README.md'
    path.write_text(path.read_text().replace(f'Release are at `{GIT_TAG}`',
                                           'Release are at v0.0.0-alpha.1', 1))
    with pytest.raises(ValueError, match='current tag text'):
        check_release_docs(candidate)
