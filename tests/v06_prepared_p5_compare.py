"""Native-observation matching; deliberately does NOT grant functional acceptance."""
import argparse
import json
from pathlib import Path
from v06_prepared_consumers import comparable, MODES


def compare_observations(actual,native):
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
        if comparable(c)!=comparable(native['cases'][target]):differences.append(name)
    assert actual['cases']['go']['result']=='PASS','Go consumer failed'
    for name in ('pure','default'):
        assert actual['cases'][name].get('crud_binary_table_and_text_controls')=='PASS','required normal consumer did not finish'
    return differences


def main():
    p=argparse.ArgumentParser();p.add_argument('--actual',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--consumer-exit',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out={'scope':'diagnostic native parity only; no new limitation accepted','functional_acceptance':'FAIL','human_disposition':'PENDING','matching':'FAIL'}
    try:
        actual=json.loads(a.actual.read_text());native=json.loads(a.native.read_text())
        assert a.consumer_exit==1 and actual['result']=='FAIL','unexpected prospective functional status'
        out['different_cases']=compare_observations(actual,native)
        assert not out['different_cases'],'new native/guest consumer difference'
        out['matching']='PASS'
    except Exception as e:out['error']=repr(e)
    finally:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    if out['matching']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
