#!/usr/bin/env python3
"""Focused metadata/identity/release-tool checks; no MariaDB build or runtime tests."""
import os
import subprocess
import sys
from common import ROOT
from verify import SOURCE_TESTS

TESTS = ['tests/test_git_identity.py', 'tests/test_runtime_validation.py',
         *SOURCE_TESTS,
         'tests/test_release_prepare.py', 'tests/test_release_plan.py',
         'tests/test_release_docs.py', 'tests/test_release_version.py',
         'tests/test_generated_release.py', 'tests/test_ci_publication_workflow.py']


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for command in ([sys.executable, 'scripts/check_version.py'],
                    [sys.executable, 'scripts/verify_generated_runtime.py'],
                    [sys.executable, '-m', 'pytest', *TESTS, '-q', '-p', 'no:cacheprovider'],
                    [sys.executable, 'benchmarks/ownedprepared/test_tools.py'],
                    [sys.executable, 'scripts/check_public.py'],
                    ['git', 'diff', '--check']):
        subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
