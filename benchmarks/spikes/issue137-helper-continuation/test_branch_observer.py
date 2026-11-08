"""Only finite observation controls; does not execute SQL or prove branch hit."""
import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('branch',Path(__file__).with_name('legacy_spare_archive.py'));branch=importlib.util.module_from_spec(spec);spec.loader.exec_module(branch)
class Root:
 closed=False
 logs=''
class Observer(unittest.TestCase):
 def test_marker_required(self):
  with self.assertRaises(TimeoutError):branch.wait_branch(Root(),0)
 def test_dead_root_not_accepted_even_with_marker(self):
  r=Root();r.closed=True;r.logs=branch.MARKER
  with self.assertRaises(RuntimeError):branch.wait_branch(r,0)
 def test_live_marker_observed(self):
  r=Root();r.logs=branch.MARKER;self.assertEqual(branch.wait_branch(r,0),branch.MARKER)
if __name__=='__main__':unittest.main()
