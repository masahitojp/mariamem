"""Reduce all30 observations, then reproduce the comparison using compact data only."""
from pathlib import Path
import argparse,copy,hashlib,json,math,statistics

def q(values,p):
    s=sorted(values);return s[max(0,math.ceil(len(s)*p)-1)]
def stats(values):
    return {'n':len(values),'p50':statistics.median(values),'p95':q(values,.95),'max':max(values)}
def reduce(raw):
    out=[]
    for r in raw:
        m=r['trace']['meta'];spans=r['trace']['spans']
        v={k:r[k] for k in ['name','arm','mode','parallel','repeat','process_wall_ms','rss_bytes','exit_code','scratch_empty','binary_sha256']}
        v.update(wall_ms=r['trace']['elapsed_ms'],cpu_ms=float(m['cpu_ms']),metadata=m,
                 span_counts={k:sum(s['kind']==k for s in spans) for k in ['fork','sample','cleanup','read','write']},
                 child_stages=[{'kind':s['kind'],'lane':s['lane'],'ms':s['end_ms']-s['start_ms']} for s in spans if s['kind'] in ['fork','sample','cleanup']])
        if r['mode']=='phases':
            v['loaders']=[{'lane':s['lane'],'db_id':s['db_id'],'total_us':s['total_us'],'prepare_us':s['durations_us']['prepare'],'phase_counts':{k:len(a) for k,a in s['durations_us'].items()},'operations_ge50ms':(s.get('operations_ge50ms') or [])} for s in r['loaders']]
        out.append(v)
    return out

def validate(rows):
    expected={(a,'warmup',p,0) for a in ['baseline','candidate'] for p in [4,8]}
    expected|={(a,'off',p,r) for a in ['baseline','candidate'] for p in [4,8] for r in range(1,6)}
    expected|={(a,'phases',8,r) for a in ['baseline','candidate'] for r in range(1,4)}
    assert len(rows)==30 and {(r['arm'],r['mode'],r['parallel'],r['repeat']) for r in rows}==expected
    for r in rows:
        assert r['exit_code']==0 and r['scratch_empty'] is True
        m=r['metadata'];p=r['parallel']
        for k,v in {'route':'Pipe','parallel':str(p),'fork_cap':str(p+1),'active_mappings_after':'0','read_cases':'50','write_cases':'20','test_exit':'0','innodb_buffer_pool_size':'16777216','innodb_read_io_threads':'1'}.items():assert m[k]==v
        for k,n in [('fork',21),('sample',21),('read',50),('write',20)]:assert r['span_counts'][k]==n
        for k in ['fork','sample','cleanup']:assert len([s for s in r['child_stages'] if s['kind']==k])==r['span_counts'][k]
        assert all(s['ms']>=0 for s in r['child_stages'])
        if r['mode']=='phases':
            assert len(r['loaders'])==21
            for s in r['loaders']:
                assert len(s['prepare_us'])==3
                for k,n in [('prepare',3),('order_insert',40),('item_insert',100),('stock_update',100),('commit',1)]:assert s['phase_counts'][k]==n
                assert not any(x.get('error') for x in s['operations_ge50ms'])
    for mode in ['warmup','off']:
        assert all('loaders' not in r for r in rows if r['mode']==mode)

def analyze(rows):
    validate(rows)
    result={'primary':{},'secondary_prepare':{},'all_suites_pass':True,'suites':30,'warmups_excluded':4,'percentiles':'p50 median; p95 nearest rank; no excluded tail samples'}
    for p in [4,8]:
        data={a:sorted([r for r in rows if r['mode']=='off' and r['parallel']==p and r['arm']==a],key=lambda r:r['repeat']) for a in ['baseline','candidate']}
        group={a:{k:stats([r[k] for r in rr]) for k in ['wall_ms','process_wall_ms','cpu_ms','rss_bytes']} for a,rr in data.items()}
        for a,rr in data.items():
            group[a]['child_stages_ms']={k:stats([s['ms'] for r in rr for s in r['child_stages'] if s['kind']==k]) for k in ['fork','sample','cleanup']}
            group[a]['sample_gt100ms']=sum(s['kind']=='sample' and s['ms']>100 for r in rr for s in r['child_stages'])
        group['paired']={k:{'delta_pct':[100*(c[k]/b[k]-1) for b,c in zip(data['baseline'],data['candidate'])],'median_delta_pct':statistics.median(100*(c[k]/b[k]-1) for b,c in zip(data['baseline'],data['candidate'])),'candidate_lower_pairs':sum(c[k]<b[k] for b,c in zip(data['baseline'],data['candidate']))} for k in ['wall_ms','cpu_ms','rss_bytes']}
        result['primary'][str(p)]=group
    for a in ['baseline','candidate']:
        rr=[r for r in rows if r['mode']=='phases' and r['arm']==a]
        values=[v/1000 for r in rr for s in r['loaders'] for v in s['prepare_us']]
        result['secondary_prepare'][a]=stats(values)|{'gt100ms':sum(v>100 for v in values),'batch_counts_gt100ms':[sum(v>100000 for s in r['loaders'] for v in s['prepare_us']) for r in rr]}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path);p.add_argument('--compact',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.raw:
        assert not a.check
        raw=a.raw.read_bytes();rows=reduce(json.loads(raw));validate(rows)
        a.compact.write_text(json.dumps({'original_observations_sha256':hashlib.sha256(raw).hexdigest(),'reduction':'All30 suites; fork/sample/cleanup durations and lanes; all secondary PREPARE times, phase counts and long operations. Nonclaimed per-call order/item/update durations discarded.','rows':rows},separators=(',',':'))+'\n')
    rows=json.loads(a.compact.read_text())['rows'];result=analyze(rows)
    for change in [lambda r:r.pop(),lambda r:r[0].update(scratch_empty=False),lambda r:r[0]['metadata'].update(active_mappings_after='1'),lambda r:r[0]['span_counts'].update(fork=20)]:
        bad=copy.deepcopy(rows);change(bad)
        try:validate(bad)
        except AssertionError:continue
        raise AssertionError('corrupt evidence accepted')
    content=json.dumps(result,indent=2)+'\n'
    if a.check:assert a.summary.read_text()==content
    else:a.summary.write_text(content)
    print('PASS: all30 suites; fixed matrix/correctness/cleanup; four negative controls; compact-only summary reproducible')
    for parallel,group in result['primary'].items():
        print('P'+parallel,'wall medians',*[round(group[x]['wall_ms']['p50'],2) for x in ['baseline','candidate']],'paired%',round(group['paired']['wall_ms']['median_delta_pct'],2),'lower pairs',group['paired']['wall_ms']['candidate_lower_pairs'])
    print('PREPARE',json.dumps(result['secondary_prepare']))
if __name__=='__main__':main()
