"""Attach point probes only in diagnostic binaries, preserving framing and SQL."""
from pathlib import Path
import shutil,json,hashlib

def prepare(w,h,mapping,arm):
    src=w/'worktree'
    rec=Path(__file__).resolve().parent
    pkg=h/'p8probe';pkg.mkdir(exist_ok=True)
    shutil.copyfile(rec/'probe.go.txt',pkg/'probe.go')
    shutil.copyfile(rec/'client.go.txt',pkg/'client.go')
    imp='probe "github.com/shibukawa/pgmem/bench/modelcase/p8probe"'
    dst=w/'temp'/('diag-src-'+arm);dst.mkdir(exist_ok=True)
    records={}
    def edit(path, pairs):
        p=Path(mapping.get(str(path),path));original=p.read_text();s=original
        for old,new in pairs:
            assert s.count(old)==1,(path.name,old,s.count(old))
            s=s.replace(old,new)
        s=s.replace('\nimport (','\nimport (\n'+imp,1)
        assert imp in s
        target=dst/(str(path.relative_to(w)).replace('/','_'))
        target.write_text(s)
        mapping[str(path)]=str(target)
        records[str(path.relative_to(w))]=[hashlib.sha256(original.encode()).hexdigest(),hashlib.sha256(s.encode()).hexdigest()]
    edit(src/'internal/guest/linked.go',[
        ('capture := &prepared.Capture{}','ctx, link := probe.New(ctx)\n capture := &prepared.Capture{}'),
        ('StartInstanceWithStopped(childIn, childOut,','StartInstanceWithStopped(&probe.Reader{Source:childIn,L:link}, &probe.Writer{Target:childOut,L:link},'),
        ('p := &Process{startupTiming:', 'p := &Process{diag:probe.From(ctx), startupTiming:')])
    edit(src/'internal/guest/guest.go',[
        ('type Process struct {','type Process struct {\n diag *probe.Link'),
        ('var headerAt time.Time','header:=probe.Now()\n var headerAt time.Time'),
        ('var msg struct {','body:=probe.Now()\n var msg struct {'),
        ('p.mu.Lock()\n\t\tch := p.pending[msg.ID]','row:=p.diag.Received(msg.ID,int(n),header,body)\n p.mu.Lock()\n ch := p.pending[msg.ID]'),
        ('ch <- response{result: msg.Result','if row!=nil{row.Notify=probe.Now()}\n ch <- response{result: msg.Result'),
        ('func (p *Process) write(ctx context.Context, b []byte) error {','func (p *Process) write(ctx context.Context, b []byte, row *probe.Row) error {'),
        ('complete := make(chan error, 1)','if row!=nil {row.Queue=probe.Now()}\n complete := make(chan error, 1)'),
        ('go func() { complete <- writeAll(p.in, b) }()', 'go func(){if row!=nil{row.Write=probe.Now()};complete<-writeAll(p.in,b)}()'),
        ('limit := 1 << 20','callAt:=probe.Now()\n limit:=1<<20'),
        ('p.pending[id] = ch','p.pending[id] = ch\n row:=p.diag.Begin(id,slot,op,13+len(sql),callAt)'),
        ('p.write(ctx, packet)','p.write(ctx, packet,row)'),('p.write(ctx, frame)','p.write(ctx,frame,nil)'),
        ('case r := <-ch:\n\t\treturn r.result, r.err','case r:=<-ch:\n row.Resume=probe.Now();return r.result,r.err')])
    edit(src/'internal/generatedgo/runtime_instance.go',[
        ('m, release = created, ownedRelease','m, release = created, ownedRelease\n probe.Register(m.Threads,in)')])
    edit(src/'internal/generatedgo/code/p1/p1_pure.go',[
        ('v169 = Fn130(m, v85)','v169 = Fn130(m, v85)\n probe.Worker(m.Threads,uint32(v167))')])
    edit(src/'internal/generatedgo/code/p6/p6_pure.go',[
        ('func Fn265(m *base.Module, l0 int32, l1 int32, l2 int32) {','func Fn265(m *base.Module, l0 int32, l1 int32, l2 int32) {\n probe.Reply(m.Threads,uint32(l0),uint32(l1))')])
    edit(h/'internal/trace/trace.go',[
        ('"encoding/json"','"encoding/json"\n"strconv"'),
        ('return &Recorder{t0: time.Now(), meta: map[string]string{}}','now:=time.Now(); return &Recorder{t0:now, meta:map[string]string{"probe_ns":strconv.FormatInt(probe.Stamp(now),10)}}')])
    edit(h/'store/fixture_test.go',[
        ('\n\tos.Exit(code)','\n probe.Save();probe.SaveClients()\n os.Exit(code)'),
        ('done = f.rec.Start("sample", "sample", t.Name())\n\t\tif err := store.LoadSample(ctx, db);','done = f.rec.Start("sample", "sample", t.Name())\n\t\tif err := store.LoadSample(probe.Lane(ctx,t.Name()), db);'),
        ('if f.sharedErr = store.LoadSample(ctx, db);','if f.sharedErr = store.LoadSample(probe.Lane(ctx,"shared"), db);')])
    p=h/'store/seed.go'
    s=p.read_text()
    start=s.index('func LoadSample(');end=s.index('\n}',start)+2
    body=s[start:end]
    body=body.replace('tx, err := db.BeginTx(ctx, nil)','log:=probe.Client(ctx);defer log.Finish()\n log.Start("begin"); tx, err := db.BeginTx(ctx,nil);log.End()')
    for var,label in [('insOrder','prepare_order'),('insItem','prepare_item'),('reserve','prepare_stock')]:
        old='\t'+var+', err := tx.PrepareContext('
        a=body.index(old);b=body.index('\n',a)
        body=body[:a]+'\tlog.Start("'+label+'");'+body[a:b].lstrip()+';log.End()'+body[b:]
    for begin,label in [('if err := insOrder.QueryRowContext','order'),('if _, err := insItem.ExecContext','item'),('if _, err := reserve.ExecContext','stock')]:
        a=body.index(begin);b=body.index('\n',body.index('}',a))
        body=body[:a]+'log.Start("'+label+'");'+body[a:b]+';log.End()'+body[b:]
    body=body.replace('return tx.Commit()','log.Start("commit");err=tx.Commit(); log.End();return err')
    edit(p,[(s[start:end],body)])
    (w/'evidence/published'/('bindings-'+arm+'.json')).write_text(json.dumps(records,indent=2)+'\n')
    return mapping
