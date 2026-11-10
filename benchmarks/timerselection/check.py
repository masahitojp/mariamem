"""Compile the exact upstream tracker methods under bounded selection profiles.

This is a C++ selection unit, not a MariaDB/WASM/runtime acceptance test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
from git_identity import require_commit


def digest(data):
    return hashlib.sha256(data).hexdigest()


def function(text, signature):
    assert text.count(signature) == 1
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    plan = json.loads((HERE/'plan.json').read_text())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require_commit(ROOT, head)
    require_commit(ROOT, plan['source_commit'])
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    args.work.mkdir(parents=True)
    source = args.work/'upstream'
    originals = {}
    for name, expected in plan['upstream_files'].items():
        url = 'https://raw.githubusercontent.com/MariaDB/server/'+plan['mariadb_source_commit']+'/'+name
        data = urllib.request.urlopen(url, timeout=60).read()
        assert digest(data) == expected, name
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        originals[name] = data.decode()
    header = source/'sql/sql_analyze_stmt.h'
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT/'guest/experimental.patch')],
                   cwd=source, check=True, capture_output=True)
    before = originals['sql/sql_analyze_stmt.h']
    after = header.read_text()
    guard = '#if (MY_TIMER_ROUTINE_CYCLES)'
    corrected = guard+' && !defined(__wasi__)'
    assert before.count(guard) == 2
    assert after == before.replace(guard, corrected)
    assert (source/'include/my_rdtsc.h').read_text() == originals['include/my_rdtsc.h']
    signatures = ['static inline double timer_tracker_frequency()', 'ulonglong measure() const']
    extracted = {name: [function(text, sig) for sig in signatures]
                 for name, text in [('before', before), ('after', after)]}
    fixture = '''extern "C" int printf(const char*, ...);
using ulonglong = unsigned long long;
struct Unit { double frequency; };
struct Info { Unit cycles; Unit microseconds; };
#ifdef __wasi__
Info sys_timer_info{{0}, {1000000}};
ulonglong my_timer_cycles(){return 0;}
#else
Info sys_timer_info{{1000000000}, {1000000}};
ulonglong my_timer_cycles(){static ulonglong x=10;return x+=20000000;}
#endif
ulonglong my_timer_microseconds(){static ulonglong x=10;return x+=20000;}
@FREQUENCY@
struct Probe { @MEASURE@ };
int main(){Probe p;auto start=p.measure();auto end=p.measure();
 double frequency=timer_tracker_frequency();double ms=1000.0*(end-start)/frequency;
 bool ok=__builtin_isfinite(ms)&&ms==20.0;
 printf("{\\"frequency\\":%.0f,\\"delta\\":%llu,\\"correct_20ms\\":%s}\\n",frequency,end-start,ok?"true":"false");
 return ok?0:3;}
'''
    cases = []
    compiler = os.environ.get('CXX', 'c++')
    version = subprocess.check_output([compiler, '--version'], text=True).splitlines()[0]
    profiles = [('wasi', ['-D__wasi__=1', '-DMY_TIMER_ROUTINE_CYCLES=29']),
                ('native_cycles', ['-DMY_TIMER_ROUTINE_CYCLES=29']),
                ('native_no_cycles', ['-DMY_TIMER_ROUTINE_CYCLES=0'])]
    for profile, flags in profiles:
        for treatment in ['before', 'after']:
            freq, measure = extracted[treatment]
            text = fixture.replace('@FREQUENCY@', freq).replace('@MEASURE@', measure)
            stem = args.work/(profile+'-'+treatment)
            cpp = stem.with_suffix('.cc')
            cpp.write_text(text)
            subprocess.run([compiler, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', *flags,
                            str(cpp), '-o', str(stem)], check=True)
            run = subprocess.run([str(stem)], text=True, capture_output=True)
            expected = 3 if profile == 'wasi' and treatment == 'before' else 0
            assert run.returncode == expected, (profile, treatment, run.stdout, run.stderr)
            cases.append(dict(profile=profile, treatment=treatment, returncode=run.returncode,
                              observed=json.loads(run.stdout), source_sha256=digest(text.encode())))
    # Reverting either half must reject the change: ticks and frequency must agree.
    controls = []
    for index in [0, 1]:
        parts = list(extracted['after'])
        parts[index] = extracted['before'][index]
        text = fixture.replace('@FREQUENCY@', parts[0]).replace('@MEASURE@', parts[1])
        cpp = args.work/('mutation'+str(index)+'.cc')
        cpp.write_text(text)
        binary = cpp.with_suffix('')
        subprocess.run([compiler, '-std=c++17', '-O2', *profiles[0][1], str(cpp), '-o', str(binary)],
                       check=True)
        run = subprocess.run([str(binary)], text=True, capture_output=True)
        assert run.returncode == 3
        controls.append(dict(reverted=signatures[index], rejected=True, observed=json.loads(run.stdout)))
    result = dict(result='SELECTION_UNIT_PASS', source_commit=head, product_source_commit=plan['source_commit'],
                  mariadb_source_commit=plan['mariadb_source_commit'], compiler=version,
                  patch_sha256=digest((ROOT/'guest/experimental.patch').read_bytes()),
                  header_before_sha256=digest(before.encode()), header_after_sha256=digest(after.encode()),
                  cases=cases, negative_controls=controls,
                  limitation='Exact methods with stub clocks; not actual guest/SQL/runtime evidence.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(result['result'])


if __name__ == '__main__':
    main()
