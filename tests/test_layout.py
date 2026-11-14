"""Path ownership stays relative to the caller's checkout, including temp roots."""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import layout


def test_paths_are_relative_and_compose_with_another_checkout(tmp_path):
    assert layout.GENERATED == Path('internal/generatedgo')
    assert layout.GENERATED_CODE == layout.GENERATED/'code'
    assert layout.BENCHMARKS == Path('benchmarks')
    assert layout.FIXTURES == Path('tests/fixtures')
    for path in [layout.GENERATED, layout.GENERATED_CODE, layout.BENCHMARKS,
                 layout.FIXTURES, *layout.MODULE_MARKERS]:
        assert not path.is_absolute()
        assert (tmp_path/path).relative_to(tmp_path) == path
    assert all((ROOT/path).is_file() for path in layout.MODULE_MARKERS)


def test_no_new_literal_root_paths_in_maintained_python():
    # Module identities, serialized contract strings and historical reproduction
    # are distinct from actual filesystem path construction.
    prefixes = ('internal/generatedgo', 'benchmarks', 'tests/fixtures')
    errors = []
    for directory in ('scripts', 'tests'):
        for path in (ROOT/directory).rglob('*.py'):
            if 'historical' in path.parts or path.name == 'layout.py':
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                    value = node.right
                    literal = value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else (value.values[0].value if isinstance(value, ast.JoinedStr) and value.values and isinstance(value.values[0], ast.Constant) and isinstance(value.values[0].value, str) else None)
                    if literal is not None:
                        if any(literal == prefix or literal.startswith(prefix+'/') for prefix in prefixes):
                            errors.append(f'{path.relative_to(ROOT)}:{node.lineno}')
    assert not errors, 'use scripts/layout.py for filesystem paths: '+', '.join(errors)
