"""Offline pin proposal only. Canonical installer remains unchanged/fail-closed."""
from pathlib import Path
import importlib.util,json,hashlib,re,unittest
S=Path(__file__).resolve().parents[2];R=Path(__file__).resolve().parent/'ci-42433100335'
P=json.loads((R/'binding-inspection.json').read_text());G=P['guest_sha256']
def load(name):
 spec=importlib.util.spec_from_file_location('proposal_'+name,S/'scripts'/('runtime_'+name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def configured():
 t,c=load('thread_lifetime'),load('crc32c');t.GUEST_SHA256=G;t.FUNCTIONS={p:(v['name'],v['new_normalized_sha256']) for p,v in P['thread_functions'].items()};c.GUEST_SHA256=G;c.BODY_SHA256=P['crc']['new_exact_sha256'];c.TABLE_OFFSET=P['crc']['new_table_offset'];return t,c
def fixture(fn):return (R/'functions'/(fn+'.go.txt')).read_text()
def files():return {'generated/base/base.go',*(x.replace('code/','generated/',1) for x in P['thread_functions'])}
def memory():return bytes(P['crc']['new_table_offset'])+bytes.fromhex((S/'tests/fixtures/pinned-crc-table.hex').read_text())
class PinProposal(unittest.TestCase):
 def test_original_guards_still_reject_new_guest(self):
  with self.assertRaises(ValueError):load('thread_lifetime').validate_inputs(G,files())
  with self.assertRaises(ValueError):load('crc32c').validate_inputs(G,memory())
 def test_proposed_exact_inputs_and_handoff(self):
  t,c=configured();t.validate_inputs(G,files());c.validate_inputs(G,memory())
  for path,info in P['thread_functions'].items():
   body=fixture(info['name']);self.assertEqual(hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest(),info['new_normalized_sha256'])
   changed=t.apply(path,body)
   if info['name']=='Fn153':self.assertEqual(changed.count('base.DeferThreadAllocationFree('),1)
   else:self.assertEqual(changed,body)
 def test_crc_preserves_every_non_computation_block(self):
  _,c=configured();old=fixture('Fn18145');new=c.apply(c.PATH,old)
  def blocks(v):
   parts=re.split(r'\n(L\d+):\n',v);return {parts[i]:parts[i+1] for i in range(1,len(parts),2)}
  a,b=blocks(old),blocks(new);self.assertEqual(set(b),set(a)-(c.CRC_BLOCKS-{'L23'}))
  self.assertTrue(all(b[k]==v for k,v in a.items() if k not in c.CRC_BLOCKS));self.assertEqual(new.count('base.CRC32C('),1)
 def test_one_more_relocation_is_rejected(self):
  t,c=configured()
  for path,info in P['thread_functions'].items():
   if not info['replacements']:continue
   old=str(info['replacements'][0]['new']);body=fixture(info['name']);wrong=body.replace(old,str(int(old)+4),1);self.assertNotEqual(wrong,body)
   with self.subTest(path=path),self.assertRaises(ValueError):t.apply(path,wrong)
  body=fixture('Fn18145');wrong=body.replace('15569536','15569540',1);self.assertNotEqual(wrong,body)
  with self.assertRaises(ValueError):c.apply(c.PATH,wrong)
 def test_crc_missing_duplicate_comparison_and_lsn_rejected(self):
  _,c=configured();body=fixture('Fn18145')
  for wrong in [body.replace('Fn18145(','Fn99999(',1),body+'\n'+body,body.replace('L36:\n','L36:\n\treturn 0\n',1),body.replace('L81:\n','L81:\n\treturn 0\n',1)]:
   with self.subTest(wrong=wrong[:30]),self.assertRaises(ValueError):c.apply(c.PATH,wrong)
 def test_guest_table_and_required_file_rejected(self):
  t,c=configured();data=memory()
  for bad_guest,bad_data in [('0'*64,data),(G,data[:-1]),(G,data[:-1]+bytes([data[-1]^1]))]:
   with self.subTest(guest=bad_guest[:8],size=len(bad_data)),self.assertRaises(ValueError):c.validate_inputs(bad_guest,bad_data)
  for missing in files():
   with self.subTest(missing=missing),self.assertRaises(ValueError):t.validate_inputs(G,files()-{missing})
 def test_memory_init_fixture_and_tls_are_pinned(self):
  self.assertEqual(hashlib.sha256(re.sub(r'\s+','',fixture('Fn67')).encode()).hexdigest(),P['memory_initialization']['new_init_compact_sha256'])
  self.assertEqual(P['memory_initialization']['tls_bytes'],505)
  self.assertTrue(P['both_hosts_identical']);self.assertEqual(P['both_hosts_generated_files'],51)
if __name__=='__main__':unittest.main()
