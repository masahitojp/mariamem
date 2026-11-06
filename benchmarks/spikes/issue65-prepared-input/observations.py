"""Account for the named prepared input observations; missing evidence fails closed."""
import json
import re

def with_suffix(names, suffixes):
    return {name+suffix for name in names for suffix in suffixes}

HEADER = {f'param{param}_{name}' for param in ('false','true') for name in ('cursor','flags8','iteration0','iteration2')}
DESCRIPTORS = {'newtypes2','type17','typeflags1','short_scalar','extra_scalar'} | {f'prefix{i}' for i in range(21)}
EXPECTED = {
    'TestG1ExecuteHeader': with_suffix(HEADER, ('','_ping','_cached')) | with_suffix({n for n in HEADER if n.startswith('paramtrue')}, ('_seed','_fresh')),
    'TestG1ZeroParamSuffix': with_suffix({'none','zero','one','two','extra'}, ('','_ping','_cached')),
    'TestG1Descriptors': with_suffix(DESCRIPTORS, ('','_seed','_ping','_cached','_fresh')),
    'TestG1SQLBounds': with_suffix({f'op{op}_n{size}' for op in (3,22) for size in (0,1048576)}, ('','_ping')) | {'op22_n1048576_execute','max_plus_one_header','max_plus_one_peer'},
    'TestG1SetOption': with_suffix({'empty','short','on','off','unknown','surplus'}, ('','_ping')),
    'TestG1FailedPrepareAlias': {'seed','failed_prepare','alias','old_handle_ping','old_handle_cached','old_handle_fresh'},
    'TestG1LongDataHeader': with_suffix({f'n{i}' for i in range(7)}, ('_seed','_no_response_ping','_state','_fresh')),
}


def selected(inventory):
    return {n:v for n,v in inventory.items() if n.endswith(('.go','.s')) or n.endswith('/data.bin')}


def require_extension(actual, baseline, fixture_sha):
    expected = dict(selected(baseline))
    name = 'cmd/issue65-wire/g1_test.go'
    if name in expected:
        raise ValueError('baseline already contains limits fixture')
    expected[name] = fixture_sha
    if selected(actual) != expected:
        raise ValueError('source must be exact baseline plus one pinned test fixture')
    return len(expected)


def analyze(log, exit_code):
    cases = re.findall(r'^--- (PASS|FAIL|SKIP): (TestG1\w+) \(([^)]+)\)$',log,re.M)
    observations=[]
    seen=set()
    for line in log.splitlines():
        if 'G1_OBSERVATION ' not in line:
            continue
        row=json.loads(line.split('G1_OBSERVATION ',1)[1])
        if set(row)!={'test','id','expected','actual','pass'} or type(row['pass']) is not bool:
            raise ValueError('invalid observation schema')
        group=row['test'].split('/')[0]
        if group not in EXPECTED or row['id'] not in EXPECTED[group]:
            raise ValueError('unknown observation identity')
        key=(group,row['id'])
        if key in seen:
            raise ValueError('duplicate observation identity')
        seen.add(key);observations.append(row)
    required={(group,name) for group,ids in EXPECTED.items() for name in ids}
    names=[n for _,n,_ in cases]
    complete=(set(names)==set(EXPECTED) and len(names)==len(EXPECTED)
              and all(s!='SKIP' for s,_,_ in cases) and seen==required
              and exit_code in (0,1) and log.endswith(('PASS\n','FAIL\n')))
    ready=(complete and exit_code==0 and log.endswith('PASS\n')
           and all(s=='PASS' for s,_,_ in cases) and all(o['pass'] for o in observations))
    return {'result':'PASS scoped G1 inputs' if ready else ('NOT_READY: contract mismatches' if complete else 'INCOMPLETE: missing execution evidence'),
            'complete':complete,'ready':ready,'exit_code':exit_code,
            'cases':[{'name':n,'result':s,'elapsed':t} for s,n,t in cases],
            'observations':observations,'mismatches':[o for o in observations if not o['pass']],
            'missing_observations':[{'group':g,'id':i} for g,i in sorted(required-seen)]}
