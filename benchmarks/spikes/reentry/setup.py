#!/usr/bin/env python3
"""Install component tests in isolated modules; production packages are untouched."""
import argparse
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-module', type=Path, required=True)
p.add_argument('--output-dir', type=Path, required=True)
p.add_argument('--wasm-tools', type=Path, required=True)
p.add_argument('--converter', type=Path, required=True)
a = p.parse_args()
templates = Path(__file__).resolve().parent
out = a.output_dir.resolve()
if out.exists():
    raise SystemExit('Use a new output directory; existing experiments are not overwritten.')
out.mkdir(parents=True)
(out / 'go.mod').write_text('module example.com/reentry-results\n\ngo 1.26.0\n')
full = out / 'module'
shutil.copytree(a.source_module.resolve(), full)
shutil.copyfile(templates / 'component-test.go.txt', full / 'generated/base/reentry_test.go')
small = out / 'semantic'
(small / 'generated').mkdir(parents=True)
(small / 'go.mod').write_text('module example.com/reentry\n\ngo 1.26.0\n')
subprocess.run([str(a.wasm_tools.resolve()), 'parse', str(templates / 'semantic-worker.wat'),
                '-o', str(small / 'worker.wasm')], check=True)
subprocess.run([str(a.converter.resolve()), '-pure', '-i', str(small / 'worker.wasm'),
                '-out-dir', str(small / 'generated'), '-o', str(small / 'generated/module.go'), '-pkg', 'generated',
                '-import', 'example.com/reentry/generated'], check=True)
shutil.copyfile(templates / 'semantic-worker-test.go.txt', small / 'generated/reentry_test.go')
print('Component modules installed. The semantic worker is a reduction, not MariaDB reentry.')
