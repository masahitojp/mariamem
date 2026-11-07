"""Compare every G2 record;ignore only the named valid fatal-output drain quantity."""
import copy

def normalized(rows):
    out={}
    for row in rows:
        key=(row['test'],row['id'])
        if key in out:raise ValueError('duplicate G2 identity')
        value=copy.deepcopy(row)
        if key==('TestG2FatalStates/mid_output','mid_output_active'):
            actual=value['actual']
            count=actual['drained_native_bytes']
            if type(count) is not int or count<0:raise ValueError('invalid native drain quantity')
            del actual['drained_native_bytes']
        out[key]=value
    return out

def compare(reference,observed):
    if reference['guest_sha256']!=observed['guest_sha256']:raise ValueError('different guest')
    a=normalized(reference['observations']);b=normalized(observed['observations'])
    differences=[{'test':k[0],'id':k[1],'reference':a.get(k),'observed':b.get(k)} for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
    return {'matched':not differences,'compared_observations':len(a),'different_records':differences,
            'ignored_quantity':'TestG2FatalStates/mid_output mid_output_active.actual.drained_native_bytes only;all other fields retained',
            'qualification':'comparison does not turn contract mismatches into PASS'}
