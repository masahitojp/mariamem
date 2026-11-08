"""Select the exact complete legacy profile in an owned producer clone only."""
import json,sys
from pathlib import Path
r=Path(sys.argv[1]).resolve();owner=Path(__file__).resolve().parents[3]
if not r.is_relative_to(owner/'build'):raise ValueError('owned build clone required')
p=json.loads((r/'guest/input.json').read_text());p['prepared_profile']='legacy-full';p.pop('native_overlay');old=json.loads((owner/'benchmarks/spikes/issue137-prepared-profile/inputs/legacy-input-entry.json').read_text());p['patches']=[old if e['file'].endswith('-native-prepared.patch') else e for e in p['patches']]
(r/'guest/input.json').write_text(json.dumps(p,indent=2)+'\n');(r/'guest/prepared_source_patch.json').write_bytes((owner/'benchmarks/spikes/issue137-prepared-profile/inputs/legacy-prepared.json').read_bytes());(r/'guest/experimental.patch').unlink()
