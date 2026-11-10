"""The manifest is source-bound and the generator consumes the selected output."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import runtime_static_image as image


def test_source_binding_detects_add_change_remove(tmp_path):
    runtime = tmp_path/'runtime'
    (runtime/'code').mkdir(parents=True)
    (runtime/'image').mkdir()
    src = runtime/'code/initial.go'
    src.write_text('selected initial bytes')
    original = image.source_hashes(runtime)
    (runtime/image.LAYOUT).write_text(json.dumps({'source_sha256':original}))
    image.verify_sources(runtime)
    src.write_text('different initial bytes')
    with pytest.raises(ValueError, match='source drift'):
        image.verify_sources(runtime)
    src.unlink()
    with pytest.raises(ValueError, match='source drift'):
        image.verify_sources(runtime)
    src.write_text('selected initial bytes')
    (runtime/'code/extra.go').write_text('new constructor initialization')
    with pytest.raises(ValueError, match='source drift'):
        image.verify_sources(runtime)


def test_generation_stages_selected_tree_and_cleans_scratch(tmp_path, monkeypatch):
    runtime = tmp_path/'selected'
    for name in ('code', 'image', 'imagelayout', 'layoutgen'):
        (runtime/name).mkdir(parents=True)
    (runtime/'code/selected.go').write_text('selected guest, not checkout guest')
    calls = []
    def run(command, *, cwd, env, check):
        staged = cwd/'internal/generatedgo'
        assert (staged/'code/selected.go').read_text() == 'selected guest, not checkout guest'
        assert command[-1] == str(runtime/image.LAYOUT)
        assert env['GOWORK'] == 'off' and env['GOTOOLCHAIN'] == 'local'
        assert check
        calls.append(cwd)
        (runtime/image.LAYOUT).write_text(json.dumps({'source_sha256':image.source_hashes(staged)}))
    monkeypatch.setattr(image.subprocess, 'run', run)
    image.generate(runtime, Path('/toolchain/bin/go'))
    assert len(calls) == 1 and not calls[0].exists()
    image.verify_sources(runtime)
