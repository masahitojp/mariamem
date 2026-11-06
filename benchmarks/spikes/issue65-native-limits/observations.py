"""Account for the named native limit observations; missing evidence fails closed."""
import json
import re

EXPECTED = {
    'TestLimitsCommands': {name+suffix for name in ('reset_connection','stmt_fetch','statistics','process_info','binlog_dump') for suffix in ('','_following')},
    'TestLimitsCapabilities': {'tls','missing_protocol41','compression_not_negotiated','compression_not_negotiated_following','deprecate_eof_not_negotiated','deprecate_eof_not_negotiated_following'},
    'TestLimitsInputHeaders': {f'n{size}_warm{warm}' for size in (1048578,16777215) for warm in ('false','true')},
    'TestLimitsOutputPacket': {f'binary{binary}_over{over}'+suffix for binary in ('false','true') for over in ('false','true') for suffix in (('','_following') if over=='false' else ('',))},
    'TestLimitsAggregate': {f'binary{binary}_{suffix}' for binary in ('false','true') for suffix in ('control','data','bounds')},
    'TestLimitsPipeWindow': {f'full_window_{mode}_{suffix}' for mode in ('overflow','eof') for suffix in ('setup','abort')} | {'independent_overflow','independent_eof'},
}


def selected(inventory):
    return {n:v for n,v in inventory.items() if n.endswith(('.go','.s')) or n.endswith('/data.bin')}


def require_extension(actual, baseline, fixture_sha):
    expected = dict(selected(baseline))
    name = 'cmd/issue65-wire/limits_test.go'
    if name in expected:
        raise ValueError('baseline already contains limits fixture')
    expected[name] = fixture_sha
    if selected(actual) != expected:
        raise ValueError('source must be exact baseline plus one pinned test fixture')
    return len(expected)


def analyze(log, exit_code):
    cases = re.findall(r'^--- (PASS|FAIL|SKIP): (TestLimits\w+) \(([^)]+)\)$',log,re.M)
    observations=[]
    seen=set()
    for line in log.splitlines():
        if 'LIMITS_OBSERVATION ' not in line:
            continue
        row=json.loads(line.split('LIMITS_OBSERVATION ',1)[1])
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
    return {'result':'PASS scoped native limits' if ready else ('NOT_READY: contract mismatches' if complete else 'INCOMPLETE: missing execution evidence'),
            'complete':complete,'ready':ready,'exit_code':exit_code,
            'cases':[{'name':n,'result':s,'elapsed':t} for s,n,t in cases],
            'observations':observations,'mismatches':[o for o in observations if not o['pass']],
            'missing_observations':[{'group':g,'id':i} for g,i in sorted(required-seen)]}
