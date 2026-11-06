import copy,json,unittest
from pathlib import Path
from compact import read
import analyze
class AnalysisTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.records=read(Path(__file__).parent);cls.trace=cls.records[0]['traces']['0']
 def test_valid_matrix(self):
  result,rows=analyze.reduce(self.records);self.assertEqual(len(rows),576);self.assertEqual(result['primary_children'],576)
 def test_duplicate_named_plugins_are_all_counted(self):
  t=copy.deepcopy(self.trace);es=t['startup']['guest']['initialization']['events'];pairs=[];begin=None
  for x in es:
   if x['name']=='plugin.uuid.begin':begin=x['offset_ns']
   if x['name']=='plugin.uuid.end':pairs.append((x['offset_ns']-begin)/1e6)
  self.assertEqual(len(pairs),2);self.assertAlmostEqual(analyze.decompose(t)['plugin.uuid'],sum(pairs))
 def test_missing_drop_order_and_unpaired_are_rejected(self):
  for kind in ['missing','drop','order','unpaired']:
   with self.subTest(kind=kind):
    t=copy.deepcopy(self.trace);i=t['startup']['guest']['initialization'];es=i['events']
    if kind=='missing':i['events']=[x for x in es if x['name']!='buffer_pool_begin']
    if kind=='drop':i['dropped_records']=1
    if kind=='order':es[1]['offset_ns']=-1
    if kind=='unpaired':i['events']=[x for x in es if x['name']!='plugin.InnoDB.end']
    with self.assertRaises((AssertionError,KeyError)):analyze.decompose(t)
 def test_matrix_and_cleanup_mutations_rejected(self):
  for kind in ['missing','duplicate','leak','oracle']:
   with self.subTest(kind=kind):
    rs=copy.deepcopy(self.records)
    if kind=='missing':rs.pop()
    if kind=='duplicate':rs[-1]=copy.deepcopy(rs[-2])
    if kind=='leak':rs[-1]['report']['cleanup_stats']['active_mappings']=1
    if kind=='oracle':rs[-1]['report']['samples'][0]['oracle']=False
    with self.assertRaises(AssertionError):analyze.reduce(rs)
if __name__=='__main__':unittest.main()
