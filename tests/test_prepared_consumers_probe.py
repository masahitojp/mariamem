"""Consumer receipt/oracle controls, not execution of either database."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from v06_prepared_consumers import compare_reference
from v06_prepared_p5_compare import compare_observations, verify_cext_profile

ROOT=Path(__file__).resolve().parents[1]


def native():
    return json.loads((ROOT/'tests/fixtures/prepared-p5-native-observation.json').read_text())


def test_failed_native_fixture_cannot_satisfy_functional_acceptance():
    r=native()
    with pytest.raises(AssertionError):compare_reference(r,r)
    assert compare_observations(r,r)==[]
    assert r['result']=='FAIL' and set(r['failures'])=={'pure','default','cext'}
    assert all(r['cases'][n]['stage']=='prepared-call' for n in ('pure','default','cext'))
    assert all(r['cases'][n]['crud_binary_table_and_text_controls']=='PASS' for n in ('pure','default','cext'))


@pytest.mark.parametrize('mutation',['missing-mode','wrong-value','wrong-error','wrong-raw-error','pool-leak','missing-normal-consumer','unknown-default'])
def test_matching_never_hides_new_failures(mutation):
    reference=native();r=copy.deepcopy(reference)
    if mutation=='missing-mode':del r['cases']['pure']
    elif mutation=='wrong-value':r['cases']['pure']['prepared_values'][1]=-18
    elif mutation=='wrong-error':r['cases']['pure']['error']='different exception'
    elif mutation=='wrong-raw-error':r['cases']['pure']['raw_syntax']['packet']='ff'
    elif mutation=='pool-leak':r['cases']['go']['modes'][0]['open_after']=1
    elif mutation=='missing-normal-consumer':del r['cases']['pure']['crud_binary_table_and_text_controls']
    else:r['cases']['default']['implementation']='unknown'
    try:different=compare_observations(r,reference)
    except AssertionError:return
    assert different,mutation


def stage_module():
    spec=importlib.util.spec_from_file_location('p5stage',ROOT/'tests/v06_prepared_p5_stage.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('mutation',['binary','guest','commit','sdk','missing-sdk','qualified'])
def test_private_staging_rejects_unbound_inputs(tmp_path,mutation):
    m=stage_module();d=tmp_path/'development';sdk=d/'product/python';sdk.mkdir(parents=True)
    (d/'mariamem-dev-host').write_bytes(b'host');(sdk/'sample.py').write_bytes(b'sdk')
    r={'contract':m.CONTRACT,'result':'UNQUALIFIED','smoke':'PASS','guest_sha256':'a'*64,'binary_sha256':m.digest(d/'mariamem-dev-host'),'source_identity':{'commit':'b'*40},'host_source_identity':{'commit':'b'*40,'files_sha256':{'python/sample.py':m.digest(sdk/'sample.py')}}}
    (d/'development.json').write_text(json.dumps(r));m.verify_inputs(d,'b'*40,'a'*64)
    if mutation=='binary':(d/'mariamem-dev-host').write_bytes(b'wrong')
    elif mutation=='sdk':(sdk/'sample.py').write_bytes(b'wrong')
    elif mutation=='missing-sdk':(sdk/'sample.py').unlink()
    else:
        if mutation=='guest':r['guest_sha256']='c'*64
        elif mutation=='commit':r['source_identity']['commit']='c'*40
        else:r['result']='READY'
        (d/'development.json').write_text(json.dumps(r))
    with pytest.raises(ValueError):m.verify_inputs(d,'b'*40,'a'*64)


def test_only_optional_explicit_cext_can_skip_without_forcing_default():
    r=native()
    r['cases']['cext']={'result':'SKIP','reason':'explicit C extension unavailable'}
    r['failures'].pop('cext')
    r['cases']['default']=copy.deepcopy(r['cases']['pure'])
    r['cases']['default']['mode']='default'
    assert compare_observations(r,r)==[]
    r['cases']['default']['implementation']='CMySQLConnection'
    assert compare_observations(r,native())==['default']


def primary_without_cext():
    r=native()
    r['cases']['cext']={'result':'SKIP','reason':'explicit C extension unavailable'}
    r['failures'].pop('cext')
    r['cases']['default']=copy.deepcopy(r['cases']['pure'])
    r['cases']['default']['mode']='default'
    return r


def test_required_default_cext_needs_real_native_control():
    with pytest.raises(ValueError,match='missing required native C-extension control'):
        compare_observations(native(),primary_without_cext())
    assert compare_observations(native(),primary_without_cext(),native())==[]


@pytest.mark.parametrize('mutation',['value','error','missing-normal','wrong-class','qualified'])
def test_secondary_reference_is_not_a_weak_fallback(mutation):
    secondary=native()
    c=secondary['cases']['cext']
    if mutation=='value':c['prepared_values'][1]=-18
    elif mutation=='error':c['error']='different native failure'
    elif mutation=='missing-normal':del c['crud_binary_table_and_text_controls']
    elif mutation=='wrong-class':c['implementation']='MySQLConnection'
    else:secondary['result']='PASS'
    try:diff=compare_observations(native(),primary_without_cext(),secondary)
    except AssertionError:return
    assert diff==['default','cext']


def cext_environment():
    return json.loads((ROOT/'tests/fixtures/prepared-p5-native-macos314-environment.json').read_text())


def test_recorded_python314_control_preserves_full_failure():
    r=json.loads((ROOT/'tests/fixtures/prepared-p5-native-macos314.json').read_text())
    assert compare_observations(native(),primary_without_cext(),r)==[]
    with pytest.raises(AssertionError):compare_reference(r,r)
    verify_cext_profile(cext_environment(),cext_environment())


@pytest.mark.parametrize('key',['os','architecture','python_minor','soabi','connector','extension_file','extension_sha256','connector_sources_sha256','direct_import','connector_have_cext','openssl'])
def test_recorded_cext_control_rejects_different_client(key):
    r=cext_environment();r[key]='different'
    with pytest.raises(AssertionError):verify_cext_profile(r,cext_environment())


@pytest.mark.parametrize('profile',['missing','wrong','valid'])
def test_cli_requires_cext_client_binding_and_keeps_functional_fail(tmp_path,monkeypatch,profile):
    import sys
    import v06_prepared_p5_compare as m
    for name,data in [('actual',native()),('primary',primary_without_cext()),('env',cext_environment())]:
        (tmp_path/(name+'.json')).write_text(json.dumps(data))
    output=tmp_path/'result.json'
    argv=['compare','--actual',str(tmp_path/'actual.json'),'--native',str(tmp_path/'primary.json'),'--native-cext',str(ROOT/'tests/fixtures/prepared-p5-native-macos314.json'),'--consumer-exit','1','--output',str(output)]
    if profile!='missing':
        if profile=='wrong':
            r=cext_environment();r['extension_sha256']='0'*64;(tmp_path/'env.json').write_text(json.dumps(r))
        argv+=['--actual-environment',str(tmp_path/'env.json'),'--native-cext-environment',str(ROOT/'tests/fixtures/prepared-p5-native-macos314-environment.json')]
    monkeypatch.setattr(sys,'argv',argv)
    if profile=='valid':m.main()
    else:
        with pytest.raises(SystemExit):m.main()
    r=json.loads(output.read_text())
    assert r['matching']==('PASS' if profile=='valid' else 'FAIL')
    assert r['functional_acceptance']=='FAIL' and r['human_disposition']=='PENDING'
