"""Account for the named G2 observations; missing evidence fails closed."""
import json
import re

from pathlib import Path
# The named set is fixed before execution and independent of candidate output.
ORACLE=json.loads(Path(__file__).with_name('g2_test.go.txt').read_text().split('const g2OracleJSON = `',1)[1].split('`',1)[0])
def suffix(names,values):return {n+s for n in names for s in values}
EXPECTED={
 'TestG2PrepareMetadata':suffix({x['name'] for x in ORACLE['prepare']}, ('','_following')),
 'TestG2TypedValues':suffix({x['name'] for x in ORACLE['values']}, ('_reusefalse','_reusetrue','_following')),
 'TestG2AdditionalTypes':{x['name']+'_trace'+str(i) for x in ORACLE['additional'] for i in range(len(x['trace']))}|{x['name']+'_following' for x in ORACLE['additional']},
 'TestG2CallChains':{x['name']+'_'+kind+str(i) for x in ORACLE['calls'] for i in range(len(x['trace'])) for kind in ('trace','following')}|{x['name']+'_close_ping' for x in ORACLE['calls']},
 'TestG2LongDataStates':suffix({x['name'] for x in ORACLE['long']}, ('','_following'))|{'reset-stream_reset','malformed_rejected','malformed_retains_stream','malformed_fresh','malformed_following'},
 'TestG2LifecycleBodies':{f'n{n}_{part}' for n in range(6) for part in ('reset','close_no_response','handle')},
 'TestG2MultiStatements':suffix({'handshake','option_on','option_off'}, ('','_following'))|{'option_on_set','option_off_set'},
 'TestG2MetadataBoundary':suffix({'ascii_alias255','unicode_alias255_bytes','literal65536'}, ('_metadata','_value','_following')),
 'TestG2LoginStates':{'initial_db','initial_db_state','missing_db','missing_db_peer','short_fixed_header','short_fixed_header_peer','truncated_auth','truncated_auth_peer','explicit_charset','explicit_charset_state'},
 'TestG2LargeMetadata':{'control_prepare','control_metadata'}|{f'over{over}_{part}' for over in ('false','true') for part in ('prepare','packet','following')},
 'TestG2FatalStates':{name+tail for name in ('partial_body','mid_output','buffered_future') for tail in ('_active','_peer','_owner','_independent','_cleanup')},
}


def selected(inventory):
    return {n:v for n,v in inventory.items() if n.endswith(('.go','.s')) or n.endswith('/data.bin')}


def require_extension(actual, baseline, fixture_sha):
    expected = dict(selected(baseline))
    name = 'cmd/issue65-wire/g2_test.go'
    if name in expected:
        raise ValueError('baseline already contains G2 fixture')
    expected[name] = fixture_sha
    if selected(actual) != expected:
        raise ValueError('source must be exact baseline plus one pinned test fixture')
    return len(expected)


def analyze(log, exit_code):
    cases = re.findall(r'^--- (PASS|FAIL|SKIP): (TestG2\w+) \(([^)]+)\)$',log,re.M)
    observations=[]
    seen=set()
    for line in log.splitlines():
        if 'G2_OBSERVATION ' not in line:
            continue
        row=json.loads(line.split('G2_OBSERVATION ',1)[1])
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
    preconditions=[o for o in observations if o['test'].split('/')[0]=='TestG2LargeMetadata'
                   and o['id'] in ('control_prepare','control_metadata','overfalse_prepare','overtrue_prepare') and not o['pass']]
    if preconditions:complete=False
    ready=(complete and exit_code==0 and log.endswith('PASS\n')
           and all(s=='PASS' for s,_,_ in cases) and all(o['pass'] for o in observations))
    return {'result':'PASS scoped G2 inputs' if ready else ('NOT_READY: contract mismatches' if complete else 'INCOMPLETE: missing execution evidence'),
            'complete':complete,'ready':ready,'exit_code':exit_code,
            'metadata_reachability_precondition_failures':preconditions,
            'cases':[{'name':n,'result':s,'elapsed':t} for s,n,t in cases],
            'observations':observations,'mismatches':[o for o in observations if not o['pass']],
            'missing_observations':[{'group':g,'id':i} for g,i in sorted(required-seen)]}
