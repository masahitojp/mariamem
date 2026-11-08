"""Receipt replay must reject missing trials/children, broken ownership and wrong pairing."""
from pathlib import Path
import copy,importlib.util,json,sys,unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'lexercandidate'))
from codec import read
spec=importlib.util.spec_from_file_location('actual_c_analysis',HERE/'analyze.py');analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis);reduce=analysis.reduce

class Replay(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.records=read(HERE/'results/observations.json')
 def test_complete_and_read_only(self):
  before=json.dumps(self.records,sort_keys=True);s,rows=reduce(self.records)
  self.assertEqual(s['primary_children'],1728);self.assertEqual(len(rows),1728)
  self.assertEqual(before,json.dumps(self.records,sort_keys=True))
 def test_each_pair_uses_its_own_repetition(self):
  rs=copy.deepcopy(self.records)
  for r in rs:
   if (r['kind'],r['mode'],r['parallel'],r['observer'])==('primary','fork',1,'off'):
    r['report']['batch_ms']=(r['rep']+1)*100*(1 if r['arm']=='baseline' else 1.1+r['rep']*.1)
  s,_=reduce(rs)
  self.assertEqual([round(r['batch_ms_change_pct'],6) for r in s['pairs']['fork-p1-off']],[10,20,30])
 def test_invalid_receipts_rejected(self):
  for failure in ['trial','duplicate','child','cleanup','negative','trace','labels','phase']:
   rs=copy.deepcopy(self.records);p=next(r for r in rs if r['kind']=='primary');on=next(r for r in rs if r['kind']=='primary' and r['observer']=='on')
   if failure=='trial':rs.pop()
   elif failure=='duplicate':next(r for r in rs if r['kind']=='primary' and r['rep']==1 and r['mode']==p['mode'] and r['arm']==p['arm'] and r['parallel']==p['parallel'] and r['observer']==p['observer'])['rep']=0
   elif failure=='child':p['report']['samples'].pop()
   elif failure=='cleanup':p['report']['cleanup_stats']['active_mappings']=1
   elif failure=='negative':next(r for r in rs if r['negative'])['exit_code']=0
   elif failure=='labels':p['report']['parallel']=99
   elif failure=='trace':on['traces'].pop('0')
   else:next(x for x in on['traces']['0']['startup']['guest']['events'] if x['name']=='server_init_complete')['offset_ns']=-1
   with self.subTest(failure=failure),self.assertRaises((AssertionError,KeyError)):reduce(rs)

if __name__=='__main__':unittest.main()
