"""Receipt-gate tests only; no SQL/runtime PASS is inferred from synthetic rows."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('routing_spike_run',ROOT/'tests/spikes/connection_routing/run.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
OLD=ROOT/'docs/reviews/v06x-connection-routing-evidence/ci-40026373681/macos-15/control.json'


class RoutingReceiptContract(unittest.TestCase):
    def control(self):
        data=json.loads(OLD.read_text())
        # Synthetic rows exercise receipt validation, not the actual new cases.
        data['cases'] += [{'row':row,'name':name,'status':'PASS'} for row,name in
                         [('R2','idle-session-state'),('R3','unknown-physical-ownership')]]
        return data

    def test_old_success_does_not_close_new_scope(self):
        self.assertFalse(runner.assess(json.loads(OLD.read_text()),'control',0)['complete'])

    def test_exact_cases_and_successful_process_required(self):
        data=self.control()
        self.assertTrue(runner.assess(data,'control',0)['complete'])
        for damage in ['missing','duplicate','failed','unknown_status','cleanup','sentinel','wrong_exit']:
            with self.subTest(damage=damage):
                broken=copy.deepcopy(data);exit_code=0
                if damage=='missing':broken['cases'].pop()
                if damage=='duplicate':broken['cases'][-1]=broken['cases'][0]
                if damage=='failed':broken['cases'][-1]['status']='FAIL'
                if damage=='unknown_status':broken['cases'][-1]['status']='UNKNOWN'
                if damage=='cleanup':broken['all_hosts_reaped']=False
                if damage=='sentinel':broken['sentinel_attempts']=1
                if damage=='wrong_exit':exit_code=1
                self.assertFalse(runner.assess(broken,'control',exit_code)['complete'])

    def test_required_connector_skip_is_not_completion(self):
        data=self.control()
        case=next(c for c in data['cases'] if c['name']=='connector-prepared')
        case['status']='SKIP';data['connector_import_error']='import failed'
        self.assertFalse(runner.assess(data,'control',1)['accepted'])
        partial=runner.assess(data,'control',1,True)
        self.assertTrue(partial['accepted'])
        self.assertFalse(partial['complete'])

    def test_new_mutations_require_their_specific_observations(self):
        for mode,observation in [('retain_session',{'marker':'A','leaked_scope':'scope-0','step':1}),
                                 ('adopt_unknown',{'requested':'B','observed':'A','unknown_owner':True})]:
            row,name=runner.MUTATIONS[mode]
            data={'all_hosts_reaped':True,'sentinel_attempts':0,
                  'cases':[{'row':row,'name':name,'status':'FAIL',
                            'error_type':'AssertionError','observation':observation}]}
            self.assertTrue(runner.assess(data,mode,1)['detected_expected_defect'])
            for damage in ['observation','case','fatal','exit']:
                with self.subTest(mode=mode,damage=damage):
                    broken=copy.deepcopy(data);exit_code=1
                    if damage=='observation':broken['cases'][0]['observation']={}
                    if damage=='case':broken['cases'][0]['name']='other-case'
                    if damage=='fatal':broken['fatal']={'stage':'setup'}
                    if damage=='exit':exit_code=0
                    self.assertFalse(runner.assess(broken,mode,exit_code)['accepted'])

    def test_existing_mutation_receipts_still_accepted(self):
        for mode in ['no_pool_check','fallback','ignore_retired','global_target']:
            data=json.loads((OLD.parent/(mode+'.json')).read_text())
            self.assertTrue(runner.assess(data,mode,1)['accepted'])


if __name__=='__main__':unittest.main()
