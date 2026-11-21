from pathlib import Path
import subprocess
import sys

harness = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
prior = '706072d8dbfa76acb23d302d6bfaa08b91c444b5:benchmarks/insert-trigger-stages/results-20261114/sum-control/harness/'
for name in ('go.mod', 'go.sum', 'store/seed.go', 'store/store.go', 'store/migrations/0001_all.sql'):
    dest = harness / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = subprocess.check_output(['git', '-C', source, 'show', prior + name])
    dest.write_bytes(data.replace(b'<PRODUCT_WORKTREE>', str(source).encode()))
(harness / 'main.go').write_bytes(Path(__file__).with_name('main.go').read_bytes())
