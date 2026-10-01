#!/usr/bin/env python3
"""Install a fail-closed diagnostic driver in an already isolated generated module."""
import argparse
from pathlib import Path
import re


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module', type=Path, required=True)
    a = p.parse_args()
    root = a.module.resolve()
    if not (root / 'go.mod').is_file():
        p.error('a separate go.mod is required before installing Go files')
    base = (root / 'generated/base/base.go').read_text()
    iface = base.split('type Wasix_32v1Imports interface {', 1)[1].split('\n}', 1)[0]
    template = Path(__file__).with_name('execution-driver.go.txt').read_text()
    methods = []
    for signature in iface.strip().splitlines():
        name = re.match(r'\s*(\w+)\(', signature).group(1)
        if re.search(r'func \(h \*host\) ' + name + r'\(', template):
            continue
        # A stub never returns success: observe the first required contract.
        methods.append('func (h *host) ' + signature.strip().replace('*Module', '*base.Module') +
                       ' { panic("unimplemented WASIX: ' + name + '") }')
    (root / 'main.go').write_text(template + '\n' + '\n'.join(methods) + '\n')
    (root / 'generated/base/spike_wait.go').write_text(
        'package base\nfunc SpikeWait(m *Module) { m.Threads.wg.Wait() }\n')


if __name__ == '__main__':
    main()
