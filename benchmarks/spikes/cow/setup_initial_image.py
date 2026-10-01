#!/usr/bin/env python3
"""Add the bounded initialized-image proof to an already isolated observer module."""
import argparse
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('module', type=Path)
    a = p.parse_args()
    assert (a.module/'go.mod').is_file()
    here = Path(__file__).parent
    (a.module/'initial_image.go').write_text((here/'initial-image.go.txt').read_text())
    (a.module/'cow_control.go').write_text((here/'profile-control.go.txt').read_text())
    main = a.module/'main.go'
    s = main.read_text()
    assert 'cowNewModule' not in s
    s = s.replace('m := generated.NewWithWASI(h, nil, h)', 'm := cowNewModule(h)\n    defer cowRelease()')
    if 'stopControl:=' not in s:
        s = s.replace('cowControl(m,fs)', 'stopControl:=cowControl(m,fs)\n    defer stopControl()')
    main.write_text(s)


if __name__ == '__main__': main()
