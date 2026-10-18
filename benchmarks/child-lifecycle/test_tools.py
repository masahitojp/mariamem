import copy
import unittest
from campaign import EXPECTED_COMMITS, validate_stamps
from reduce import events

class IdentityAndTraceOracle(unittest.TestCase):
 def binaries(self):
  return {v:{kind:{'stamp':f'binary: go1.26.8\n build\tvcs.revision={sha}\n build\tvcs.modified=false\n build\tCGO_ENABLED=0\n'} for kind in ('child','host')} for v,sha in EXPECTED_COMMITS.items()}
 def test_exact_stamps(self):validate_stamps(self.binaries())
 def test_outer_main_stamp_is_rejected(self):
  b=self.binaries();b['control']['child']['stamp']=b['control']['child']['stamp'].replace(EXPECTED_COMMITS['control'],'df90c096a269d448a50ac44ac92f88e47619d58e')
  with self.assertRaises(AssertionError):validate_stamps(b)
 def test_absent_dirty_or_missing_binary_is_rejected(self):
  for mutation in (lambda b:b['observed']['host'].update(stamp='binary: go1.26.8'),lambda b:b['control']['child'].update(stamp=b['control']['child']['stamp'].replace('modified=false','modified=true')),lambda b:b['control'].pop('host')):
   b=self.binaries();mutation(b)
   with self.assertRaises(AssertionError):validate_stamps(b)
 def test_trace_gaps_and_nonmonotonicity_are_rejected(self):
  t={'events':[{'name':'begin','offset_ns':0},{'name':'frame','offset_ns':4},{'name':'end','offset_ns':8}]}
  self.assertEqual(events(t)['frame'],4)
  for mutation in (lambda e:e.pop(),lambda e:e[1].update(offset_ns=9),lambda e:e[1].update(name='begin')):
   bad=copy.deepcopy(t);mutation(bad['events'])
   with self.assertRaises(AssertionError):events(bad)

if __name__=='__main__':unittest.main()
