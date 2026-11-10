"""Exercise the actual identity helper against shallow/full local Git history."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'user.name=Fixture', '-c',
                                   'user.email=fixture@example.invalid', '-c',
                                   'commit.gpgsign=false', '-C', str(repo), *args],
                                  text=True, stderr=subprocess.PIPE).strip()


def main():
    workflow = (ROOT / '.github/workflows/wasi-timer-selection.yml').read_text()
    anchor = ('      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09\n'
              '        with:\n          fetch-depth: 0\n')
    assert workflow.count(anchor) == 1, 'identity check requires complete history'
    with tempfile.TemporaryDirectory(prefix='timer-checkout-') as temporary:
        directory = Path(temporary)
        origin = directory / 'origin'
        origin.mkdir()
        git(origin, 'init', '--quiet')
        git(origin, 'commit', '--quiet', '--allow-empty', '-m', 'baseline')
        baseline = git(origin, 'rev-parse', 'HEAD')
        git(origin, 'commit', '--quiet', '--allow-empty', '-m', 'candidate')
        head = git(origin, 'rev-parse', 'HEAD')
        clone = directory / 'shallow'
        git(directory, 'clone', '--quiet', '--depth=1', origin.as_uri(), str(clone))
        require_commit(clone, head)
        try:
            require_commit(clone, baseline)
        except ValueError as error:
            assert 'could not get object info' in str(error)
        else:
            raise AssertionError('shallow clone unexpectedly has baseline')
        git(clone, 'fetch', '--quiet', '--unshallow')
        require_commit(clone, baseline)
        require_commit(clone, head)
    print(json.dumps({'result': 'PASS', 'shallow_missing_baseline_reproduced': True,
                      'full_history_identity_passes': True, 'workflow_full_history': True}))


if __name__ == '__main__':
    main()
