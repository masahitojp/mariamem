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


def configure_fixture_stage(candidate, stage):
    source = candidate / 'python/mariamem/_version.py'
    before = runpy.run_path(str(source))
    text = re.sub(r'^STAGE = .*$', f'STAGE = {stage!r}', source.read_text(), flags=re.M)
    text = re.sub(r'^SERIAL = .*$', f'SERIAL = {1 if stage else 0}', text, flags=re.M)
    source.write_text(text)
    after = runpy.run_path(str(source))
    update_fixture_docs(candidate, before, after)


def update_fixture_docs(candidate, before, after):
    for name in DOCS:
        path = candidate / name
        text = path.read_text().replace(before['GIT_TAG'], after['GIT_TAG'])
        path.write_text(re.sub(r'(?<![\w.])' + re.escape(before['PYTHON_VERSION']) + r'(?![\w.])',
                               lambda _: after['PYTHON_VERSION'], text))


def advance_fixture_version(source):
    before = runpy.run_path(str(source))
    # A stable next patch stays stable; a prerelease advances its serial.
    field = "SERIAL" if before["STAGE"] else "PATCH"
    source.write_text(re.sub(rf'^{field} = \d+', f'{field} = {before[field] + 1}', source.read_text(), flags=re.M))
    return before, runpy.run_path(str(source))


@pytest.mark.parametrize("stage", ["", "alpha", "beta", "rc"])
def test_next_version_with_stale_examples_blocks_guard(candidate, stage):
    configure_fixture_stage(candidate, stage)
    source = candidate / 'python/mariamem/_version.py'
    _, after = advance_fixture_version(source)
    expected = after["GIT_TAG"]
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


@pytest.mark.parametrize("stage", ["", "alpha", "beta", "rc"])
def test_next_version_docs_can_be_updated_without_checker_changes(candidate, stage):
    configure_fixture_stage(candidate, stage)
    before, after = advance_fixture_version(candidate / 'python/mariamem/_version.py')
    update_fixture_docs(candidate, before, after)
    assert check_release_docs(candidate)['tag'] == after['GIT_TAG']


def test_plain_current_version_text_is_checked(candidate):
    path = candidate / 'README.md'
    path.write_text(path.read_text().replace(f'Release are at `{GIT_TAG}`',
                                           'Release are at v0.0.0-alpha.1', 1))
    with pytest.raises(ValueError, match='current tag text'):
        check_release_docs(candidate)
