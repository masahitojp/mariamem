#!/usr/bin/env python3
"""Install observer into an independent copy of the accepted generated module."""
from pathlib import Path
import argparse


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('module', type=Path)
    a = p.parse_args()
    assert (a.module/'go.mod').is_file()
    here = Path(__file__).parent
    (a.module/'generated/base/spike_profile.go').write_text((here/'profile-base.go.txt').read_text())
    (a.module/'cow_control.go').write_text((here/'profile-control.go.txt').read_text())
    path = a.module/'main.go'
    s = path.read_text()
    assert 'cowControl(' not in s
    s = s.replace('    w.SetFS(entropyFS{fs})', '    if image:=os.Getenv("COW_IMAGE"); image!="" { if err:=base.SpikeLoadFS(fs,image); err!=nil {panic(err)} }\n    w.SetFS(entropyFS{fs})')
    s = s.replace('    trace("SPIKE instantiated")', '    stopControl:=cowControl(m,fs)\n    defer stopControl()\n    trace("SPIKE instantiated")')
    s = s.replace('    trace("SPIKE all generated workers joined")', '    if dir:=os.Getenv("COW_EXPORT");dir!="" {if err:=base.SpikeExportFS(fs,dir);err!=nil{panic(err)}}\n    trace("SPIKE all generated workers joined")')
    path.write_text(s)


if __name__ == '__main__':
    main()
