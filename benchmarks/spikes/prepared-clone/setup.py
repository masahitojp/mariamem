#!/usr/bin/env python3
"""Install only into a copy of the previous isolated CoW module."""
import argparse
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('module',type=Path);a=p.parse_args()
assert (a.module/'go.mod').is_file()
here=Path(__file__).parent
(a.module/'generated/base/prepared_spike.go').write_text((here/'prepared-base.go.txt').read_text())
main=a.module/'main.go';s=main.read_text();assert 'PreparedLoad' not in s
s=s.replace('    w.SetFS(entropyFS{fs})', '''    if dir:=os.Getenv("PREPARED_FS_IMAGE");dir!="" {
        maps,err:=base.PreparedLoad(fs,dir,os.Getenv("PREPARED_FS_MODE"));if err!=nil{panic(err)}
        defer func(){if err:=maps.Close();err!=nil{panic(err)}}()
    }
    w.SetFS(entropyFS{fs})''')
s=s.replace('cowControl(m,fs)', 'cowControl(m,fs,h.WasiStubs)')
s=s.replace('    trace("SPIKE all generated workers joined")', '''    if dir:=os.Getenv("PREPARED_EXPORT");dir!="" {if err:=base.PreparedExport(fs,dir);err!=nil{panic(err)}}
    trace("SPIKE all generated workers joined")''')
main.write_text(s)
control=a.module/'cow_control.go';s=(here.parent/'cow/profile-control.go.txt').read_text()
s=s.replace('fs *base.MemFS)', 'fs *base.MemFS, wasi *base.WasiStubs)')
s=s.replace('\tserver :=', '\tmux.HandleFunc("/runtime",func(w http.ResponseWriter,r *http.Request){json.NewEncoder(w).Encode(base.PreparedRuntime(m,wasi))})\n\tserver :=')
control.write_text(s)
assert 'HandleFunc("/runtime"' in s
