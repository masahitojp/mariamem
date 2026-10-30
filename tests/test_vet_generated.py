"""The generated-code exception must never disable handwritten-code checks."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('package,disabled',[
    ('github.com/masahitojp/mariamem/internal/generatedgo/code/p8',True),
    ('github.com/masahitojp/mariamem/internal/generatedgo/code/base',False),
    ('github.com/masahitojp/mariamem/internal/generatedgo',False),
    ('github.com/masahitojp/mariamem/internal/host',False),
    ('github.com/masahitojp/mariamem/internal/generatedgo/code/p8_other',False),
])
def test_vet_scope(tmp_path, monkeypatch, package, disabled):
    path=Path(__file__).resolve().parents[1]/'scripts/vet_generated.py'
    spec=importlib.util.spec_from_file_location('vet_scope',path)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    cfg=tmp_path/'vet.cfg';cfg.write_text(json.dumps({'ImportPath':package}))
    monkeypatch.setenv('MARIAMEM_VET_TOOL','/tool/vet')
    monkeypatch.setattr(sys,'argv',[str(path),str(cfg)])
    commands=[]
    monkeypatch.setattr(tool.subprocess,'run',lambda args:commands.append(args) or SimpleNamespace(returncode=3))
    with pytest.raises(SystemExit) as exit:
        tool.main()
    assert exit.value.code==3
    assert ('-unreachable=false' in commands[0]) == disabled
    assert commands[0][-1]==str(cfg)


@pytest.mark.parametrize('package,light', [
    ('example/internal/generatedgo/code/p8', True),
    ('example/internal/generatedgo/code/base', False),
    ('example/internal/generatedgo/code', False),
    ('example/internal/host', False),
])
def test_daily_vet_retains_full_handwritten_checks_and_valid_fact_protocol(tmp_path, monkeypatch, package, light):
    import vet_generated as tool
    cfg = tmp_path/'vet.cfg'; cfg.write_text(json.dumps({'ImportPath': package}))
    monkeypatch.setenv('MARIAMEM_VET_TOOL', '/tool/vet')
    monkeypatch.setenv('MARIAMEM_VET_PROFILE', 'daily')
    monkeypatch.setattr(sys, 'argv', ['vet_generated.py', str(cfg)])
    calls = []
    monkeypatch.setattr(tool.subprocess, 'run', lambda args: calls.append(args) or SimpleNamespace(returncode=0))
    with pytest.raises(SystemExit) as result: tool.main()
    assert result.value.code == 0
    assert calls == [['/tool/vet', *(['-buildtag=true'] if light else []), str(cfg)]]
