"""Real full-file profile guard controls, without compiling or running SQL."""
import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'scripts'))
from prepared_source_patch import inputs,check_profile_source
from guest_input import apply_series
class Profiles(unittest.TestCase):
 def test_exact_profiles_and_corruption(self):
  with tempfile.TemporaryDirectory(dir=R/'build/experiment-work/issue137/temp') as td:
   t=Path(td)
   for profile in ['native-text','legacy-full']:
    root=t/profile;source=root/'source';root.mkdir()
    pin=json.loads((R/'guest/input.json').read_text());cfg=json.loads((R/('guest/prepared_source_patch.json' if profile=='native-text' else 'benchmarks/spikes/issue137-prepared-profile/inputs/legacy-prepared.json')).read_text())
    pin['prepared_profile']=profile
    if profile=='legacy-full':
     pin.pop('native_overlay');old=json.loads((R/'benchmarks/spikes/issue137-prepared-profile/inputs/legacy-input-entry.json').read_text());pin['patches']=[old if e['file'].endswith('-native-prepared.patch') else e for e in pin['patches']]
    for name in ['guest/input.json','guest/prepared_source_patch.json']:(root/name).parent.mkdir(parents=True,exist_ok=True)
    (root/'guest/input.json').write_text(json.dumps(pin));(root/'guest/prepared_source_patch.json').write_text(json.dumps(cfg))
    for name in [cfg['patch_file'],'tests/fixtures/prepared-p2-source-functions.json','tests/fixtures/prepared-param-order-functions.json']:
     p=root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/name,p)
    shutil.copytree(R/'build/experiment-work/issue137/temp/profile-baseline',source)
    entry=next(e for e in pin['patches'] if e['file']==cfg['patch_file']);apply_series(root,source,{'patches':[entry]});check_profile_source(source,root)
    pin.pop('prepared_profile');(root/'guest/input.json').write_text(json.dumps(pin))
    with self.assertRaisesRegex(ValueError,'explicit prepared profile'):inputs(root)
    pin['prepared_profile']=profile;(root/'guest/input.json').write_text(json.dumps(pin))
    changed=source/'libmysqld/libmysql.c';changed.write_bytes(changed.read_bytes()+b'\n/* unexpected edit */\n')
    with self.assertRaisesRegex(ValueError,'changed'):check_profile_source(source,root)
if __name__=='__main__':unittest.main()
