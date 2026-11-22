from pathlib import Path
import json
w=Path.cwd();src=w/'worktree';tmp=w/'temp';mapping={}
def edit(rel,pairs):
    p=src/rel;s=p.read_text()
    for a,b in pairs:
        assert s.count(a)==1,(rel,a)
        s=s.replace(a,b)
    out=tmp/p.name;out.write_text(s);mapping[str(p)]=str(out)
edit('internal/timing/timing.go',[
 ('dir        string','guestReader func() ([]byte,error)\n dir string'),
 ('// ReadGuest copies','''func BindGuestReader(ctx context.Context, reader func()([]byte,error)) {
    if t,ok:=ctx.Value(key{}).(*Trace);ok { t.mu.Lock();t.guestReader=reader;t.mu.Unlock() }
}
// ReadGuest copies'''),
 ('data, err := os.ReadFile(filepath.Join(transfer, "startup-timing.json"))','''t.mu.Lock();reader:=t.guestReader;t.mu.Unlock()
 var data []byte
 var err error
 if reader!=nil {data,err=reader()} else {data,err=os.ReadFile(filepath.Join(transfer,"startup-timing.json"))}''')])
edit('internal/guest/linked.go',[('generatedgo.StartInstanceWithStopped(childIn,','generatedgo.StartInstanceObserved(ctx, childIn,')])
edit('internal/generatedgo/runtime_instance.go',[
 ('"errors"','"errors"\n"context"\n"os"\n"github.com/masahitojp/mariamem/internal/timing"'),
 ('var libraryMode sync.Once','''var libraryMode sync.Once
func StartInstanceObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),captures ...*prepared.Capture)(<-chan error,<-chan error){
    stopped:=make(chan error,1)
    done:=runObserved(ctx,in,out,stderr,transfer,restore,guestTiming,onFailure,newMemoryModule,func(err error){stopped<-err},generated.Start,captures...)
    return stopped,done
}'''),
 ('\t// CLI diagnostic entrypoints','''return runObserved(context.Background(),in,out,stderr,transfer,restore,guestTiming,onFailure,construct,onStopped,start,captures...)
}
func runObserved(ctx context.Context,in io.Reader,out,stderr io.Writer,transfer string,restore []prepared.Entry,guestTiming bool,onFailure func(error),construct func(*host)(*base.Module,func()error,error),onStopped func(error),start func(*base.Module),captures ...*prepared.Capture)<-chan error{
 // CLI diagnostic entrypoints'''),
 ('\t\tvar maps *base.PreparedFiles','''if guestTiming && os.Getenv("FORK_GUEST_CLOCK")=="1" {
     timing.BindGuestReader(ctx,func()([]byte,error){
         f,err:=fs.OpenFile("snapshot-out/startup-timing.json",0,0)
         if err!=nil{return nil,err};defer f.Close()
         return io.ReadAll(io.LimitReader(f,128*1024+1))
     })
 }
 timing.Mark(ctx,"runtime/maps_begin")
 var maps *base.PreparedFiles'''),
 ('created, ownedRelease, allocErr := construct(h)','''timing.Mark(ctx,"runtime/module_begin")
 created, ownedRelease, allocErr := construct(h)
 timing.Mark(ctx,"runtime/module_ready")'''),
 ('if err = executeGuest(m, start);','timing.Mark(ctx,"runtime/execute_begin")\n if err = executeGuest(m, start);')])
(tmp/'overlay.json').write_text(json.dumps({'Replace':mapping}))

# Bind generated functions to the exact guest/audited symbol table used in #233.
import gzip,hashlib,re,subprocess
audit=subprocess.check_output(['git','-C',src,'show','7c5893b3:benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'])
symbol_bytes=gzip.decompress(audit)
assert hashlib.sha256(symbol_bytes).hexdigest()=='1f8dcd20057090cde400f1439d0cc9d1c933b16490ba8ecd22269d909f1fe475'
prov=json.loads((src/'internal/generatedgo/provenance.json').read_bytes())
assert prov['guest_sha256']=='869ffee51c519e4ef725bbc0c0049dd7f121e1070166ad43a5f356094891164a'
symbols=dict(line.split(':',1) for line in symbol_bytes.decode().splitlines() if ':' in line)
expected={5749: 'mysql_server_init', 5583: 'init_embedded_server', 5434: '_ZL13ha_maria_initPv', 18602: '_ZL11innodb_initPv', 4170: 'my_load_defaults', 4178: 'handle_options', 14538: '_Z18process_key_cachesPFiPKcP12st_key_cachePvES3_', 4245: 'init_key_cache', 14768: '_ZL17plugin_initializeP11st_mem_rootP13st_plugin_intPiPPcb', 14769: '_ZL20plugin_do_initializeP13st_plugin_intRj', 14770: '_ZL10plugin_addP11st_mem_rootbPK25st_mysql_const_lex_stringPS1_m', 13514: '_Z20open_and_lock_tablesP3THDRK14DDL_options_stP10TABLE_LISTbjP19Prelocking_strategy', 15242: '_Z14servers_reloadP3THD', 13044: '_Z16init_read_recordP11READ_RECORDP3THDP5TABLEP10SQL_SELECTP9SORT_INFOibb', 21001: '_Z26finalize_encryption_pluginPv'}
assert all(symbols[str(k)]==v for k,v in expected.items())
code=src/'internal/generatedgo/code'
count={}
for p in sorted(code.glob('p*/p*_pure.go')):
    s=p.read_text();before=s
    for n in expected:
        pattern=rf'^func Fn{n}\(m \*base\.Module[^\n]*\{{\n'
        s,k=re.subn(pattern,lambda match:match[0]+f'\tdefer base.MeasureForkPhase(m, {n})()\n',s,flags=re.M)
        count[n]=count.get(n,0)+k
    if p.name=='p0_pure.go':
        start=s.index('func Fn5583(')
        end=s.index('\n}',start)
        prefix=s[start:end]
        prefix,markers=re.subn(r'^([ \t]*)Fn227\(m, (int32\(\d+\))\)$',lambda x:f'{x[1]}base.MarkEmbeddedStartup(m, {x[2]})\n{x[1]}Fn227(m, {x[2]})',prefix,flags=re.M)
        assert markers==9
        s=s[:start]+prefix+s[end:]
    if before!=s:
        assert hashlib.sha256(before.encode()).hexdigest()==prov['files_sha256']['code/'+str(p.relative_to(code))]
        f=tmp/p.name;f.write_text(s);mapping[str(p)]=str(f)
assert set(count.values())=={1},count
p=code/'base/base.go'
f=tmp/'base.go';f.write_text(p.read_text()+'\n'+(w/'evidence/recipe/measure_fn.go.txt').read_text());mapping[str(p)]=str(f)
p=src/'internal/generatedgo/runtime_instance.go'
f=Path(mapping[str(p)]);s=f.read_text()
a='timing.Mark(ctx,"runtime/execute_begin")'
assert s.count(a)==1
f.write_text(s.replace(a,'''if guestTiming && os.Getenv("FORK_GUEST_CLOCK")=="1" {
    read,cleanup:=base.RecordForkPhases(m)
    defer cleanup()
    timing.BindForkPhases(ctx,func()([]byte,error){return json.Marshal(read())})
 }
 '''+a).replace('"context"','"context"\n"encoding/json"'))
p=src/'internal/timing/timing.go';f=Path(mapping[str(p)]);s=f.read_text()
s=s.replace('guestReader func()', 'Phase json.RawMessage `json:"phase,omitempty"`\n phaseReader func()([]byte,error)\n guestReader func()')
s=s.replace('// ReadGuest copies','''func BindForkPhases(ctx context.Context, reader func()([]byte,error)) {
    if t,ok:=ctx.Value(key{}).(*Trace);ok { t.mu.Lock();t.phaseReader=reader;t.mu.Unlock() }
}
// ReadGuest copies''')
s=s.replace('reader:=t.guestReader;t.mu.Unlock()', 'reader:=t.guestReader;phase:=t.phaseReader;t.mu.Unlock()\n if phase!=nil {t.Phase,_=phase()}')
f.write_text(s)
(w/'evidence'/'functions.json').write_text(json.dumps(expected,indent=2)+'\n')
(tmp/'overlay.json').write_text(json.dumps({'Replace':mapping}))
