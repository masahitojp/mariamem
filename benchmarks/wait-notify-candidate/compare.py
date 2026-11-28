import collections,gzip,hashlib,json,os,pathlib,re,shutil,statistics,subprocess,time
B=pathlib.Path(os.environ.get('WAIT_NOTIFY_WORKSPACE',str(pathlib.Path(__file__).resolve().parent.parent))).resolve();T=B/'temp';E=B/'evidence'; out=E/'normal';out.mkdir(exist_ok=False)
for arm in ('control','candidate'):
 r=json.loads((E/('build-'+arm+'.json')).read_text());assert hashlib.sha256((T/(arm+'.test')).read_bytes()).hexdigest()==r['binary_sha256']
env=dict(os.environ,GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
for k in list(env):
 if k.startswith(('AIO_','SEED_','IO_GATE','WAIT_NOTIFY')) or k in ('MODELCASE_DSN','GODEBUG','MARIAMEM_TIMING_DIR','RESPONSE_PIPE','MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE','SKIP_READ_BODY','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY'):env.pop(k,None)
(out/'environment.json').write_text(json.dumps({k:env[k] for k in ('GOMAXPROCS','GOGC','MODELCASE_MATCHED','MARIA_AUDIT_OF','REVENUE_PREAGG','MARIA_ASYNC_CLOSE')},indent=2)+'\n')
pattern='^Test(ListOrders|GetOrder|TopProducts|SearchProducts|RevenueByCategory|CreateOrder|CancelOrder|ShipOrder|DeleteUser|ApplyDiscount)$'
rows=[];traces=[]
def run(arm,kind,block,slot):
 trace=T/'trace.json';usage=T/'time.txt';trace.unlink(missing_ok=True)
 e=dict(env,MODELCASE_TRACE=str(trace));start=time.monotonic()
 p=subprocess.run(['/usr/bin/time','-v','-o',str(usage),str(T/(arm+'.test')),'-test.v','-test.parallel=8','-test.timeout=30s','-test.run='+('^TestMatchedSemantics$' if kind=='precheck' else pattern)],cwd=T,env=e,capture_output=True,text=True,timeout=40)
 wall=(time.monotonic()-start)*1000
 (out/f'output-{len(rows):02d}.txt').write_text(p.stdout+p.stderr)
 assert p.returncode==0,(arm,p.stdout[-3000:],p.stderr[-1000:])
 d=json.loads(trace.read_text());counts=collections.Counter(s['kind'] for s in d['spans']);names=collections.Counter(s['name'] for s in d['spans'])
 if kind!='precheck':assert (counts['read'],counts['write'],names['sample'],names['fork'],names['final_cleanup'])==(50,20,21,20,1)
 text=usage.read_text()
 def field(n):return float(re.search(r'^\s*'+re.escape(n)+r':\s*([\d.]+)',text,re.M)[1])
 phases=collections.defaultdict(list)
 for s in d['spans']:phases[s['name']].append(s['end_ms']-s['start_ms'])
 row=dict(index=len(rows),arm=arm,kind=kind,block=block,slot=slot,suite_ms=d['elapsed_ms'],process_ms=wall,cpu_ms=1000*(field('User time (seconds)')+field('System time (seconds)')),rss_kib=field('Maximum resident set size (kbytes)'),sample_ge400=sum(x>=400 for x in phases['sample']),max_sample_ms=max(phases['sample'],default=0),phases={k:dict(n=len(v),median_ms=statistics.median(v),max_ms=max(v)) for k,v in phases.items()},returncode=p.returncode,load=os.getloadavg())
 rows.append(row);traces.append(dict(row=row,trace=d));(out/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
 with gzip.open(out/'traces.json.gz','wt') as z:json.dump(traces,z,separators=(',',':'))
 print(kind,block,slot,arm,'process_ms',round(wall,3),'sample_max',round(row['max_sample_ms'],3),flush=True)
for i,arm in enumerate(('control','candidate')):run(arm,'precheck',-1,i)
for block in range(10):
 assert shutil.disk_usage(T).free>16*1024**3
 for slot,arm in enumerate(('control','candidate','candidate','control') if block%2==0 else ('candidate','control','control','candidate')):run(arm,'measured',block,slot)
assert len(rows)==42
print('COMPLETE 20/arm; all first retained',flush=True)
