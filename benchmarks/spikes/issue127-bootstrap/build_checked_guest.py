#!/usr/bin/env python3
"""Canonical development builder with prepared-source check before compilation."""
import importlib.util
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo/'scripts'))
spec = importlib.util.spec_from_file_location('builder', repo/'scripts/build_generated_guest.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
original = builder.observed_run


def run(*args, **kwargs):
    result = original(*args, **kwargs)
    if kwargs.get('phase') == 'guest:prepare:0':
        subprocess.run([sys.executable, Path(__file__).with_name('check_source.py'),
                        '--source', repo/'build/source', '--output',
                        '/output/prepared-check.json'], check=True)
    return result


builder.observed_run = run
sys.argv = [str(repo/'scripts/build_generated_guest.py'), '--development-output', '/output/artifact']
builder.main()
