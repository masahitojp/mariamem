"""Wheel staging must not introduce source files absent from a clean checkout."""
from pathlib import Path


def test_python_license_mirrors_match_source_inputs():
    root = Path(__file__).resolve().parents[1]
    for source in (root / 'licenses').iterdir():
        if source.is_file():
            mirror = root / 'python/licenses' / source.name
            assert mirror.is_file(), f'missing checkout license mirror: {mirror.name}'
            assert mirror.read_bytes() == source.read_bytes(), f'stale license mirror: {mirror.name}'
