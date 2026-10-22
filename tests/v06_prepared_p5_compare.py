"""Native-observation matching; deliberately does NOT grant functional acceptance."""
import argparse
import json
from pathlib import Path
from v06_prepared_consumers import comparable, MODES


def compare_observations(actual,native,native_cext=None):
    expected={*MODES,'go'}
    assert set(native['cases'])==set(actual['cases'])==expected,'missing mode'
    # Preserve the failed prospective success oracle. Matching a native failure
    # is a separate diagnostic outcome, never a rewritten functional PASS.
    expected_failures={'pure','default'}
    if native['cases']['cext'].get('result')!='SKIP':expected_failures.add('cext')
    assert native['result']=='FAIL' and set(native['failures'])==expected_failures,'unexpected native observation'
    differences=[]
    for name,c in actual['cases'].items():
        if name=='cext' and c.get('result')=='SKIP':continue
        target=name
        if name=='default':
            assert c.get('implementation') in ('MySQLConnection','CMySQLConnection'),'unknown default implementation'
            target='cext' if c['implementation']=='CMySQLConnection' else 'pure'
        reference=native['cases'][target]
        if target=='cext' and reference.get('result')=='SKIP':
            if native_cext is None:
                raise ValueError('missing required native C-extension control for '+name)
            reference=native_cext['cases']['cext']
            assert native_cext['result']=='FAIL' and reference.get('implementation')=='CMySQLConnection' and reference.get('result')=='FAIL','invalid secondary C-extension reference'
            assert reference.get('crud_binary_table_and_text_controls')=='PASS','secondary native consumer incomplete'
        if comparable(c)!=comparable(reference):differences.append(name)
    assert actual['cases']['go']['result']=='PASS','Go consumer failed'
    for name in ('pure','default'):
        assert actual['cases'][name].get('crud_binary_table_and_text_controls')=='PASS','required normal consumer did not finish'
    return differences


def verify_cext_profile(actual,reference):
    # Fixed observations only apply to the same client ABI, binary and sources.
    for r in (actual,reference):
        assert r.get('direct_import')=='PASS' and r.get('connector_have_cext') is True,'C-extension unavailable'
    for key in ('os','architecture','python_minor','soabi','connector','extension_file','extension_sha256','connector_sources_sha256'):
        assert actual.get(key) and actual[key]==reference.get(key),'native C client profile differs: '+key
    assert actual['python_minor']=='3.14','canonical Python minor required'
    # Record patch versions verbatim; no claim of identical Python/OpenSSL builds.
    av=actual.get('openssl','').split();rv=reference.get('openssl','').split()
    assert len(av)>1 and len(rv)>1 and av[0]==rv[0]=='OpenSSL','invalid OpenSSL profile'
    assert av[1].split('.')[:2]==rv[1].split('.')[:2],'native OpenSSL series differs'


def main():
    p=argparse.ArgumentParser();p.add_argument('--actual',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--native-cext',type=Path);p.add_argument('--actual-environment',type=Path);p.add_argument('--native-cext-environment',type=Path);p.add_argument('--consumer-exit',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out={'scope':'diagnostic native parity only; no new limitation accepted','functional_acceptance':'FAIL','human_disposition':'PENDING','matching':'FAIL'}
    try:
        actual=json.loads(a.actual.read_text());native=json.loads(a.native.read_text())
        assert a.consumer_exit==1 and actual['result']=='FAIL','unexpected prospective functional status'
        needs_cext=any(c.get('implementation')=='CMySQLConnection' for c in actual['cases'].values()) and native['cases']['cext'].get('result')=='SKIP'
        if needs_cext:
            assert a.native_cext and a.actual_environment and a.native_cext_environment,'required C native profile missing'
            ae=json.loads(a.actual_environment.read_text());ne=json.loads(a.native_cext_environment.read_text())
            verify_cext_profile(ae,ne)
            out['cext_client_environments']={'actual':ae,'native':ne}
        out['different_cases']=compare_observations(actual,native,json.loads(a.native_cext.read_text()) if a.native_cext else None)
        if needs_cext:out['reference_profiles']=['fresh-linux-native','recorded-macos-python314-native-cext']
        assert not out['different_cases'],'new native/guest consumer difference'
        out['matching']='PASS'
    except Exception as e:out['error']=repr(e)
    finally:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    if out['matching']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
