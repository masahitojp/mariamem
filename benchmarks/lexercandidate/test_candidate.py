"""Finite experiment workflow: acquisition must not masquerade as acceptance."""
from pathlib import Path
import re,unittest
S=Path(__file__).resolve().parents[2]
def validate(text):
 assert 'branches: [experiment/lexer-candidate]' in text
 assert 'contents: read' in text and 'continue-on-error:' not in text
 def job(name):
  m=re.search(r'^  '+name+r':\n(.*?)(?=^  \S|\Z)',text,re.M|re.S);assert m,name;return m[1]
 guest=job('guest');reference=job('reference');native=job('translation')
 assert 'ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3' in guest
 assert 'scripts/git_identity.py inspect HEAD' in guest and 'GITHUB_SHA' in guest
 assert 'c_source.py --check' in guest and '--development-output /tmp/lexer-guest' in guest
 assert 'needs: [guest, reference]' in native
 assert 'runner: [macos-15, ubuntu-24.04]' in native and 'ci_translate.py' in native
 assert '${{ github.sha }}' in guest and '${{ github.sha }}' in reference and '${{ github.sha }}' in native
 assert 'mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1' in reference
 assert '--native-port 3307' in reference
 assert 'regenerate_release_guest.py' not in native and 'operation=release' not in text
class Workflow(unittest.TestCase):
 def test_contract_and_mutations(self):
  text=(S/'.github/workflows/lexer-candidate.yml').read_text();validate(text)
  mutations=[('branches: [experiment/lexer-candidate]','branches: [main]'),('contents: read','contents: write'),('c_source.py --check','c_source.py'),('--development-output /tmp/lexer-guest',''),('needs: [guest, reference]','needs: []'),('runner: [macos-15, ubuntu-24.04]','runner: [ubuntu-24.04]'),('ci_translate.py','skip.py'),('--native-port 3307','--native-port 3306'),('805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1','0'*64)]
  for old,new in mutations:
   self.assertIn(old,text)
   with self.subTest(old=old),self.assertRaises(AssertionError):validate(text.replace(old,new))
if __name__=='__main__':unittest.main()
