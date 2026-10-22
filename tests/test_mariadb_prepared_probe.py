"""Failure controls for the bounded other-driver replay; no database execution."""
import copy
import unittest
from v06_prepared_mariadb_probe import require_complete, require_binary


def good():
    c = {'result': 'PASS', 'binary_execution_observed': True,
         'following_query': [[1]], 'cleanup_errors': []}
    return {'result': 'PASS', 'cases': {
        'nul_projection': dict(c, row=['A\0B', '410042', 3, {'type': 'bytes', 'hex': '410042'}]),
        'prepared_call': dict(c, resultsets=[[[7]], [[8]]], terminal_drained=True)}}


class Oracle(unittest.TestCase):
    def test_complete_control(self):
        require_complete(good())

    def test_truncation_error_or_missing_binary_execution_cannot_pass(self):
        for mutation in ('nul', 'hex', 'length', 'binary', 'call', 'terminal', 'witness', 'following', 'cleanup', 'native-fail', 'missing'):
            with self.subTest(mutation=mutation):
                r=copy.deepcopy(good());n=r['cases']['nul_projection'];c=r['cases']['prepared_call']
                if mutation=='nul':n['row'][0]='A'
                elif mutation=='hex':n['row'][1]='41'
                elif mutation=='length':n['row'][2]=1
                elif mutation=='binary':n['row'][3]['hex']='41'
                elif mutation=='call':c['resultsets']=[[[7]]]
                elif mutation=='terminal':c['terminal_drained']=False
                elif mutation=='witness':c['binary_execution_observed']=False
                elif mutation=='following':c['following_query']=[]
                elif mutation=='cleanup':c['cleanup_errors']=[{'errno':2014}]
                elif mutation=='native-fail':r['result']='FAIL'
                else:del r['cases']['prepared_call']
                with self.assertRaises(AssertionError):require_complete(r)

    def test_text_fallback_or_missing_counter_cannot_prove_binary(self):
        b={'Com_stmt_prepare':3,'Com_stmt_execute':4}
        require_binary(b,{'Com_stmt_prepare':4,'Com_stmt_execute':5})
        for a in ({},b,{'Com_stmt_prepare':4,'Com_stmt_execute':4}):
            with self.subTest(after=a):
                with self.assertRaises(AssertionError):require_binary(b,a)
