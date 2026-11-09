#!/usr/bin/env python3
"""Bounded CI handoff: selected formal producer -> raw binding-review inputs.

A successful command provides new bytes, not binding or public acceptance.
The same artifacts must feed the remaining #134/#132 checks.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from common import ROOT
from dev_guest import external_output, source_identity, write
from experiment_disk import DiskGuard, DiskLimit, run_guarded, GIB
from git_identity import require_commit
from guest_preparation_context import resolve


class ProducerBudget:
    """Count all owned build/SDK/download/Go-cache/output paths, without overlap."""
    def __init__(self, paths, floor, budget):
        paths = [Path(p).resolve() for p in paths]
        if any(a == b or a.is_relative_to(b) or b.is_relative_to(a)
               for i, a in enumerate(paths) for b in paths[i+1:]):
            raise ValueError('overlapping producer budget paths')
        self.guards = [DiskGuard(p, floor, budget) for p in paths]
        self.budget = int(budget * GIB)
        self.peak = 0
        self.minimum_free = None

    def check(self):
        values = [g.check() for g in self.guards]
        used = sum(v['owned_bytes'] for v in values)
        free = min(v['free_bytes'] for v in values)
        self.peak = max(self.peak, used)
        self.minimum_free = free if self.minimum_free is None else min(free, self.minimum_free)
        if used > self.budget:
            raise DiskLimit('combined producer/SDK/cache/output exceeds budget')
        return {'owned_bytes': used, 'peak_owned_bytes': self.peak,
                'free_bytes': free, 'minimum_free_bytes': self.minimum_free}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--budget-gib', type=float, default=24)
    p.add_argument('--min-free-gib', type=float, default=8)
    p.add_argument('--build-timeout', type=int, default=7200)
    p.add_argument('--translation-timeout', type=int, default=1800)
    a = p.parse_args()
    require_commit(ROOT, a.source_commit)
    identity = source_identity(ROOT)
    if identity['commit'] != a.source_commit:
        p.error('checkout differs from the requested producer source_commit')
    inputs = resolve(ROOT, a.engine, a.profile)
    out = external_output(ROOT, a.output)
    guard = ProducerBudget([ROOT/'build', '/work', '/root/.wasixcc', out], a.min_free_gib, a.budget_gib)
    guard.check()
    out.mkdir(parents=True)
    env = dict(os.environ, GOCACHE=str(out/'go-cache'), GOPATH=str(out/'go-path'),
               GOMODCACHE=str(out/'go-path/pkg/mod'), TMPDIR=str(out/'tmp'), GOTMPDIR=str(out/'tmp'),
               MARIAMEM_PHASE_TRACE=str(out/'phases.jsonl'))
    (out/'tmp').mkdir()
    report = {'source_commit': a.source_commit, 'selection': inputs['selection'],
              'resolved_sha256': inputs['resolved_sha256'], 'result': 'INCOMPLETE',
              'binding': 'NOT_REVIEWED', 'public_acceptance': 'NOT_RUN', 'phases': [],
              'budget_gib': a.budget_gib, 'min_free_gib': a.min_free_gib}
    commands = [
        ('independent-guest-builds', a.build_timeout, [sys.executable, ROOT/'scripts/build_generated_guest.py',
         '--engine', a.engine, '--profile', a.profile, '--repetitions', '2',
         '--development-output', out/'guest']),
        ('translation-for-binding-review', a.translation_timeout, [sys.executable, ROOT/'scripts/regenerate_release_guest.py',
         '--development', '--engine', a.engine, '--profile', a.profile, '--translation-only',
         '--guest-dir', out/'guest', '--output', out/'review'])]
    try:
        for name, timeout, command in commands:
            started = time.monotonic()
            with (out/(name+'.txt')).open('w') as log:
                code = run_guarded(command, guard, env=env, output=log, interval=10, timeout=timeout)
            report['phases'].append({'name': name, 'exit_code': code, 'wall_seconds': time.monotonic()-started})
            if code:
                raise RuntimeError(name + ' failed; inspect phase log')
        report['result'] = 'BINDING_REVIEW_REQUIRED'
    except BaseException as exc:
        report.update(result='FAILED', exception=type(exc).__name__, message=str(exc))
        raise
    finally:
        report.update(peak_owned_bytes=guard.peak, minimum_free_bytes=guard.minimum_free)
        write(out/'producer.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
