"""Bind a diagnostic timeline to exact sites on the fixed product source."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

w=Path(sys.argv[1]).resolve()
t=w/'temp'; src=w/'worktree'; h=t/'harness'
recipe=Path(__file__).resolve().parent
pkg=h/'timeline';pkg.mkdir(exist_ok=True)
shutil.copyfile(recipe/'timeline.go.txt',pkg/'timeline.go')
shutil.copyfile(recipe/'reader_test.go.txt',pkg/'reader_test.go')
o=t/'overlay';o.mkdir(exist_ok=True)
mapping={};hashes={}
imp='"github.com/shibukawa/pgmem/bench/modelcase/timeline"'

def edit(path,replacements,region=None):
    original=path.read_text()
    i=0;j=len(original)
    if region:
        i=original.index('func '+region+'(')
        j=original.index('\n}',i)+2
    body=original[i:j]
    for old,new in replacements:
        assert body.count(old)==1,(path.name,old,body.count(old))
        body=body.replace(old,new)
    data=original[:i]+body+original[j:]
    assert data.count('\nimport (')==1
    data=data.replace('\nimport (','\nimport (\n'+imp)
    relative=str(path.relative_to(w))
    dest=o/relative.replace('/','_')
    dest.write_text(data)
    mapping[str(path)]=str(dest)
    hashes[relative]=dict(before=hashlib.sha256(original.encode()).hexdigest(),after=hashlib.sha256(data.encode()).hexdigest())

edit(h/'main.go',[
    ('beginCPU:=processCPU()','traces:=timeline.Batch(n);ordinal:=0\n beginCPU:=processCPU()'),
    ('_, err = st.Exec','timeline.Begin(&traces[ordinal])\n _, err = st.Exec'),
    ('it.UnitPriceCents)\n\t\t\tmust(err)','it.UnitPriceCents)\n timeline.End(&traces[ordinal]);ordinal++\n must(err)'),
    ('flag.Parse(); run()','flag.Parse(); run(); timeline.Save()')])
edit(src/'internal/guest/linked.go',[('StartInstanceWithStopped(childIn, childOut,',
     'StartInstanceWithStopped(&timeline.Reader{Source:childIn}, &timeline.Writer{Target:childOut},')])
edit(src/'internal/guest/guest.go',[
    ('var headerAt time.Time','traceHeader:=timeline.Now()\n var headerAt time.Time'),
    ('var msg struct {','traceBody:=timeline.Now()\n var msg struct {'),
    ('p.mu.Lock()\n\t\tch := p.pending[msg.ID]','timeline.GotFrame(p,msg.ID,int(n),traceHeader,traceBody,timeline.Now())\n p.mu.Lock()\n ch := p.pending[msg.ID]'),
    ('ch <- response{result: msg.Result','if row:=timeline.Matches(msg.ID);row!=nil{row.Mark(timeline.Notify)}\n ch <- response{result: msg.Result'),
    ('complete := make(chan error, 1)','row:=timeline.Current();if row!=nil {row.Mark(timeline.QueueAcquired)}\n complete := make(chan error, 1)'),
    ('go func() { complete <- writeAll(p.in, b) }()','go func(){if row!=nil {row.Mark(timeline.Write)};complete<-writeAll(p.in,b)}()'),
    ('limit := 1 << 20','callAt:=timeline.Now()\n limit := 1 << 20'),
    ('p.pending[id] = ch','p.pending[id] = ch\n timeline.Bind(p,id,slot,13+len(sql),callAt)'),
    ('case r := <-ch:\n\t\treturn r.result, r.err','case r := <-ch:\n if row:=timeline.Matches(id);row!=nil{row.Mark(timeline.Resume)}\n return r.result,r.err')])
edit(src/'internal/mysqlwire/wire.go',[
    ('ctx, cancel := context.WithTimeout(context.Background(), w.timeout)\n\tdefer cancel()\n\ttype outcome', 'timeline.Mark(timeline.Monitor)\n ctx,cancel:=context.WithTimeout(context.Background(),w.timeout)\n defer cancel()\n type outcome'),
    ('case result = <-completed:\n','case result = <-completed:\n timeline.Mark(timeline.MonitorResume)\n'),
    ('return result.result, result.err','timeline.Mark(timeline.MonitorEnd)\nreturn result.result,result.err'),
    ('for _, reply := range replies {','for _, reply := range replies {\n if request[0]==23 {timeline.Mark(timeline.WireSend)}')])
edit(src/'internal/mysqlwire/prepared_execute.go',[
    ('if !s.execute {','timeline.Mark(timeline.Wire)\n if !s.execute {')])
code=src/'internal/generatedgo/code'
edit(code/'p1/p1_pure.go',[('v169 = Fn130(m, v85)','v169 = Fn130(m, v85)\n if r:=timeline.Matches(uint32(v167));r!=nil {r.Mark(timeline.Worker)}')], 'Fn267')
edit(code/'p7/p7_pure.go',[('mBase := m.M','defer timeline.OnSQL(unsafe.Pointer(m))()\n mBase := m.M')],'Fn5581')
edit(code/'p4/p4_pure.go',[('mBase := m.M','defer timeline.OnTrigger(unsafe.Pointer(m))()\n mBase := m.M')],'Fn15566')
edit(code/'p6/p6_pure.go',[('mBase := m.M','timeline.OnReply(uint32(l0),uint32(l1))\n mBase := m.M')],'Fn265')
(t/'overlay.json').write_text(json.dumps({'Replace':mapping}))
(w/'evidence/published/bindings.json').write_text(json.dumps(hashes,indent=2)+'\n')
