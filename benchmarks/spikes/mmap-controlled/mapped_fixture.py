"""Replay the existing golden memory32 matrix on reserved anonymous memory."""
import json
import shutil


def check(r):
    project = r.TEMP/'mapped-fixture'
    shutil.copytree(r.TEMP/'regression', project)
    pkg = project/'module/fixture'
    (pkg/'memory_mapping.go').write_text((r.ROOT/'internal/generatedgo/code/base/memory_mapping.go').read_text().replace('package base', 'package fixture', 1))
    (pkg/'mapped.go').write_text('''package fixture
func NewMapped() (*Module,func()error) {
 b,e:=NewMemoryMapping(65536,3*65536);if e!=nil{panic(e)}
 m:=NewWithMemory(b.Bytes(),65536);m.prepareMemoryGrow=b.Grow
 return m,b.Close
}
''')
    p = project/'module/main.go'
    s = p.read_text().replace('m := fixture.New()', 'm, release := fixture.NewMapped()')
    s = s.replace('\t}\n\tm, release := fixture.NewMapped()', '\t\tif e:=release();e!=nil{panic(e)}\n\t}\n\tm, release := fixture.NewMapped()')
    s = s.replace('\tbase := &m.Memory()[0]', '''\tdefer func(){if e:=release();e!=nil{panic(e)};stats:=fixture.MemoryMappingStats();if stats["active_mappings"]!=0 || stats["creates"]!=stats["releases"]{panic("fixture ownership leak")};fmt.Fprintln(os.Stderr,"mapped fixture ownership PASS",stats)}()
\tbase := &m.Memory()[0]''')
    p.write_text(s)
    r.run('deterministic-mapped-memory32-regression', [r.GO, 'run', '.', project/'inputs/matrix.json'], cwd=project/'module')
    actual = [json.loads(line) for line in (r.EVIDENCE/'deterministic-mapped-memory32-regression.log').read_text().splitlines() if line.startswith('{')]
    golden = json.loads((r.HERE/'reference-results.json').read_text())
    assert [[row[key] for key in golden['keys']] for row in actual] == golden['rows']
    r.record.update(mapped_fixture_case_count=len(actual), mapped_fixture_traps=sum(row['trap'] for row in actual))
    r.save()
