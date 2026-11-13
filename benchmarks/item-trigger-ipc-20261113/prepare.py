from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];ref='d73acc145acfdd8a0f1303d82cc03e78bfffb0f1';prefix='benchmarks/empty-write-pgmem-20261113/harness/'
for f in subprocess.check_output(['git','ls-tree','-r','--name-only',ref,prefix],text=True).splitlines():
 p=r/'temp/maria'/f[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show',ref+':'+f]))
p=r/'temp/maria/store/fixture_test.go';s=p.read_text();s=s.replace('f.rec.Set("server_version", version(ctx, db))','f.rec.Set("server_version", version(ctx, db))\n if err:=store.ConfigureProbe(ctx,db);err!=nil{return err}',1)
s=s.replace('code := m.Run()','code := m.Run()')
s=s.replace('\tos.Exit(code)','if err:=pgmem.ExperimentDump(os.Getenv("ITEM_EVENTS_PATH"));err!=nil{panic(err)}\n\tos.Exit(code)')
s=s.replace('if err := store.LoadSample(ctx, db); err != nil {','if err := store.LoadSample(context.WithValue(ctx,"mariamem_benchmark_label",t.Name()), db); err != nil {',1)
s=s.replace('\t\tdone()\n\t\treturn db\n\t}', '\t\tdone()\n if err:=store.FinishProbe(context.WithValue(ctx,"mariamem_benchmark_label",t.Name()),db);err!=nil{t.Fatal(err)}\n\t\treturn db\n\t}',1)
a=s.index('\tf.shared = func() *sql.DB {');b=s.index('\n\tf.close =',a)
s=s[:a]+''' f.shared = func() *sql.DB {
 f.once.Do(func(){db:=openInProcess(srv);readerCtx:=context.WithValue(ctx,"mariamem_benchmark_label","reader");done:=f.rec.Start("sample","sample","shared");f.sharedErr=store.LoadSample(readerCtx,db);done();if f.sharedErr==nil{f.sharedErr=store.FinishProbe(readerCtx,db)};if f.sharedErr==nil{f.sharedDB=db}else{db.Close()}})
 return f.sharedDB
 }
'''+s[b:]
s=s.replace('t.Cleanup(func() { db.Close(); s.Close() })','t.Cleanup(func() { if err:=db.Close();err!=nil{t.Error(err)};if err:=s.Close();err!=nil{t.Error(err)} })').replace('snap.Close()\n\t\tsrv.Close()','if err:=snap.Close();err!=nil{panic(err)}\n\t\tif err:=srv.Close();err!=nil{panic(err)}')
p.write_text(s)
p=r/'temp/maria/store/seed.go';s=p.read_text().replace('"sort"','"sort"\n mariamem "github.com/masahitojp/mariamem"')
s=s.replace('func LoadSample(ctx context.Context, db *sql.DB) error {','''func LoadSample(ctx context.Context, db *sql.DB) error {
 label,_:=ctx.Value("mariamem_benchmark_label").(string)
 sampleStart:=mariamem.ExperimentNowNS()
 defer func(){mariamem.ExperimentRecordClient(label,"sample",0,sampleStart,mariamem.ExperimentNowNS())}()
 itemIndex:=0
''')
s=s.replace('''if _, err := insItem.ExecContext(ctx, id, it.ProductID, it.Quantity, it.UnitPriceCents); err != nil {
				return err
			}''','''itemStart:=mariamem.ExperimentNowNS()
 _,itemErr:=insItem.ExecContext(ctx,id,it.ProductID,it.Quantity,it.UnitPriceCents)
 mariamem.ExperimentRecordClient(label,"item",itemIndex,itemStart,mariamem.ExperimentNowNS());itemIndex++
 if itemErr!=nil{return itemErr}
 if err:=CheckPrefix(ctx,tx,id);err!=nil{return err}''')
p.write_text(s)
(r/'evidence/plan.json').write_text(json.dumps({'question':'attribute sample detail INSERT total-recalc trigger versus request/response transfer and remaining driver/protocol costs','source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','harness_commit':ref,'baseline':'normal DSN interpolation true, original 16MiB, original writeVec, no empty-write optimization','arms':['full SUM trigger','incremental total trigger','no INSERT total trigger, repair after timed load'],'primary':'P1/P8 x3 arms x3 rotating rounds, 70 cases each; 1 warmup/cell','observer_controls':'full P8 off/on3 pairs','pilots':'prefix validation each arm P1, 1 writing case','budgets':{'gib':10,'min_free_gib':12,'build_s':1800,'process_s':130,'total_measure_s':1200},'boundaries':'same monotonic clock, actual DB/request ID, host write start, guest frame received, first nonempty reply write, host frame read, client Exec interval','decomposition':'client=before host write + inbound + guest service/response construction + outbound + after host read; not pure OS CPU','trigger_contrast':'identical 100 item INSERT calls and parameters; incremental isolates SUM-subquery removal; no-trigger isolates whole total-update body','integrity':'repair/restore outside timed LoadSample then totals, stock, audit and all70 tests; no repair speedup claim','profiling':'SQL profiling disabled in canonical WASIX; no C build or guessed C function index','stop':'fixed counts; preserve failures and explicit missing evidence; no adoption'},indent=2))
