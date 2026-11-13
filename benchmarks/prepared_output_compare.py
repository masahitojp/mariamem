#!/usr/bin/env python3
"""Bounded manual A/B prepared-output measurement; no performance PASS threshold."""
import argparse, datetime, decimal, hashlib, json, platform, statistics, subprocess, sys, time
from pathlib import Path

def value(x):
    if isinstance(x,(bytes,bytearray)): return {'hex':bytes(x).hex()}
    if isinstance(x,datetime.datetime): return {'datetime':x.isoformat()}
    if isinstance(x,decimal.Decimal): return {'decimal':str(x)}
    return x

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['baseline-host','candidate-host','sdk-root','output']:p.add_argument('--'+n,type=Path,required=True)
    for n in ['baseline-source','candidate-source']:p.add_argument('--'+n,required=True)
    p.add_argument('--pairs',type=int,default=5);p.add_argument('--iterations',type=int,default=7)
    a=p.parse_args();assert a.pairs>=3 and a.iterations>=3 and not a.output.exists()
    sys.path.insert(0,str(a.sdk_root/'python'));import mariamem,pymysql,mysql.connector
    hosts={'baseline':a.baseline_host,'candidate':a.candidate_host};origins={'baseline':a.baseline_source,'candidate':a.candidate_source}
    info={}
    for k,h in hosts.items():
        b=subprocess.check_output(['go','version','-m',h],text=True)
        assert 'vcs.revision='+origins[k] in b and 'vcs.modified=false' in b
        assert 'go1.26.10' in b and 'CGO_ENABLED=0' in b
        info[k]={'sha256':hashlib.sha256(h.read_bytes()).hexdigest(),'source_commit':origins[k],'buildinfo':b.replace(str(h),'mariamem-host')}
    report={'scope':'single-machine prepared output query time + retained RSS; no threshold or total upgrade-cost claim','platform':platform.platform(),'client':mysql.connector.__version__,'pairs':a.pairs,'iterations':a.iterations,'hosts':info,'runs':[]}
    fingerprints={};stamp=datetime.datetime(2020,1,2,3,4,5,6007)
    expected=[(i,-i,i+0.5,decimal.Decimal(f'{i}.25'),stamp,bytes([i%251])*64) for i in range(1000)]
    sql='SELECT id,n,f,amount,created,payload FROM output_perf WHERE id < ? ORDER BY id'
    for pair in range(a.pairs):
        for label in (['baseline','candidate'] if pair%2==0 else ['candidate','baseline']):
            run={'pair':pair,'variant':label,'cases':{}}
            with mariamem.start(host_binary=str(hosts[label])) as db:
                with pymysql.connect(**db.connection_info(),autocommit=True) as c:
                    with c.cursor() as q:
                        q.execute('SELECT VERSION()');version=q.fetchone()[0];assert version.startswith('12.3.3');run['engine_version']=version
                        q.execute('CREATE TABLE output_perf(id INT PRIMARY KEY,n INT,f DOUBLE,amount DECIMAL(12,2),created DATETIME(6),payload VARBINARY(64)) ENGINE=InnoDB')
                        q.executemany('INSERT INTO output_perf VALUES(%s,%s,%s,%s,%s,%s)',expected)
                with mysql.connector.connect(**db.connection_info(),use_pure=True,autocommit=True) as c:
                    for name,query,args,wanted in [('one',sql,(1,),expected[:1]),('thousand',sql,(1000,),expected),('blob64k',"SELECT REPEAT(CAST('x' AS BINARY), ?) AS payload",(65536,),[(b'x'*65536,)])]:
                        with c.cursor(prepared=True) as q:
                            samples=[]
                            for i in range(a.iterations+1):
                                start=time.perf_counter_ns();q.execute(query,args);rows=q.fetchall();elapsed=time.perf_counter_ns()-start
                                assert len(rows)==len(wanted)
                                # Connector may expose bytearray; normalize it without dropping value/type checks.
                                norm=[[value(x) for x in row] for row in rows];assert norm==[[value(x) for x in row] for row in wanted],(label,name)
                                signature=hashlib.sha256(json.dumps({'columns':[(d[0],d[1]) for d in q.description],'rows':norm},sort_keys=True).encode()).hexdigest()
                                assert fingerprints.setdefault(name,signature)==signature,(label,name,'output differs')
                                if i:samples.append(elapsed)
                            run['cases'][name]={'samples_ns':samples,'median_ns':statistics.median(samples),'fingerprint':signature}
                pid=db._session._process.pid
                run['retained_rss_kib']=int(subprocess.check_output(['ps','-o','rss=','-p',str(pid)],text=True).strip())
            report['runs'].append(run)
            a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    report['ratios']={}
    for name in ['one','thousand','blob64k']:
        ratios=[]
        for pair in range(a.pairs):
            values={r['variant']:r['cases'][name]['median_ns'] for r in report['runs'] if r['pair']==pair};ratios.append(values['candidate']/values['baseline'])
        report['ratios'][name]={'candidate_over_baseline_by_pair':ratios,'median_ratio':statistics.median(ratios)}
    report['correctness']='PASS: every measured result and metadata name/type matches expected values and peer'
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['ratios'],indent=2))
if __name__=='__main__':main()
