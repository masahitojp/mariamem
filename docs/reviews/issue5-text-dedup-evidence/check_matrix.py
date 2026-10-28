"""Assert archived native/guest equality; baseline intentionally exits nonzero."""
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text())
assert len(data) == 28, "incomplete matrix"
differences = []
for case in data:
    def canonical(value):
        return (value['outcome'], value.get('affected'),
                sorted(json.dumps(row, sort_keys=True) for row in value.get('rows', [])))
    if canonical(case['native']) != canonical(case['guest']):
        differences.append(case['label'])
print(json.dumps({'cases': len(data), 'differences': differences}, indent=2))
sys.exit(bool(differences))
