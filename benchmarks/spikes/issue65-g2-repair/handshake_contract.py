"""Human-approved short fixed-header contract;preserve historical raw evidence."""
import copy,hashlib
CONTRACT='issue65-short-fixed-header-1043-v1'
ORIGINAL_FIXTURE_SHA256='a13951d5117558b1ccfa5df7b32edb0ddc68f9d0e2a7b41a6899fa8b0751efb4'
KEY=('TestG2LoginStates/short_fixed_header','short_fixed_header')
OLD=b'\t\t\t\twant = "legacy1045/28000"\n\t\t\t\tpass = e == nil && errno == 1045 && state == "28000"'
NEW=b'\t\t\t\twant = "native1043/08S01"\n\t\t\t\tpass = e == nil && errno == 1043 && state == "08S01"'

def fixture(raw):
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_FIXTURE_SHA256 or raw.count(OLD)!=1:
        raise ValueError('original handshake fixture changed')
    return raw.replace(OLD,NEW)

def reference_for_comparison(original):
    """Adjust one approved expectation,not observed bytes or execution metadata."""
    result=copy.deepcopy(original);found=[]
    for row in result['observations']:
        if (row['test'],row['id'])!=KEY:continue
        if row['expected']!='legacy1045/28000':raise ValueError('unexpected historical expectation')
        actual=row['actual'];packet=bytes.fromhex(actual['packet'])
        if (actual['error']!='<nil>' or len(packet)<9 or packet[0]!=255 or
            int.from_bytes(packet[1:3],'little')!=1043 or packet[3:9]!=b'#08S01'):
            raise ValueError('saved packet does not satisfy approved1043/08S01 contract')
        row['expected']='native1043/08S01';row['pass']=True;found.append(row)
    if len(found)!=1:raise ValueError('missing/duplicate short fixed-header observation')
    # Keep original complete/ready/exit_code/cases/mismatches unchanged: this
    # object supplies comparison rows only,never a new runtime PASS receipt.
    return result

def adjudicate(original):
    adjusted=reference_for_comparison(original)
    rows=adjusted['observations']
    if not original['complete'] or len(rows)!=241 or original['missing_observations']:
        raise ValueError('complete241-observation evidence required')
    return {'contract':CONTRACT,'human_decision':'adopt native1043/08S01 for short fixed handshake header',
            'historical_runtime_result':original['result'],'new_runtime_executed':False,
            'observations':241,'satisfy_current_contract':sum(r['pass'] for r in rows),
            'remaining_current_contract_mismatches':[r for r in rows if not r['pass']],
            'adjusted_observation':{'test':KEY[0],'id':KEY[1],'old_expected':'legacy1045/28000','new_expected':'native1043/08S01'},
            'scope':'saved evidence assessment only;not a fresh approved-fixture runtime execution or public adoption'}
