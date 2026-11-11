"""Exact upstream initializer with deterministic clocks; not a speed benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from selection import function
from source import prepare_inputs


def sha(data):
    return hashlib.sha256(data).hexdigest()


FIXTURE = r'''
extern "C" int printf(const char*, ...);
using ulonglong = unsigned long long;
@TYPES@
@ROUTINES@
#define MY_TIMER_ROUTINE_CYCLES 29
#define MY_TIMER_ITERATIONS 1000000
#define HAVE_CLOCK_GETTIME 1
#define HAVE_GETTIMEOFDAY 1
#define HAVE_SYS_TIMES_H 1
#define HAVE_TIMES 1
#define CLOCK_MONOTONIC 1
#ifndef NO_MONOTONIC
#define MY_CLOCK_ID 1
#endif
#ifdef OTHER_CLOCK
#undef MY_CLOCK_ID
#define MY_CLOCK_ID 6
#endif
#ifdef SECONDS_CLOCK
#define HAVE_TIME 1
#endif
#ifdef FTIME_CLOCK
#define HAVE_SYS_TIMEB_H 1
#define HAVE_FTIME 1
#endif
static ulonglong cc, nc, uc, mc, tc;
ulonglong my_timer_cycles(){++cc;
#ifdef CYCLES_AVAILABLE
return 1000000+cc*1000;
#else
return 0;
#endif
}
ulonglong my_timer_nanoseconds(){return 1000000+(++nc)*100;}
ulonglong my_timer_microseconds(){return 100+(++uc)*10;}
ulonglong my_timer_milliseconds(){++mc;
#ifdef ZERO_CLOCK
return 0;
#else
#ifdef ZERO_FIRST
if(mc==1)return 0;
#endif
return 100+mc/1001;
#endif
}
ulonglong my_timer_ticks(){return 100+(++tc);}
@FUNCTIONS@
void print_unit(const char* name, my_timer_unit_info v){
 printf("\"%s\":[%llu,%llu,%llu,%llu]",name,v.routine,v.overhead,v.frequency,v.resolution);
}
int main(){MY_TIMER_INFO info={};my_timer_init(&info);
 printf("{\"milliseconds_calls\":%llu,\"timers\":{",mc);
 print_unit("cycles",info.cycles);printf(",");
 print_unit("nanoseconds",info.nanoseconds);printf(",");
 print_unit("microseconds",info.microseconds);printf(",");
 print_unit("milliseconds",info.milliseconds);printf(",");
 print_unit("ticks",info.ticks);printf("}}\n");return 0;}
'''
PROFILES = [
    ('wasi_no_cycles', ['-D__wasi__=1'], True),
    ('wasi_pfs', ['-D__wasi__=1', '-DHAVE_PSI_INTERFACE=1'], False),
    ('wasi_cycles', ['-D__wasi__=1', '-DCYCLES_AVAILABLE=1'], False),
    ('native_no_cycles', [], False),
    ('native_cycles', ['-DCYCLES_AVAILABLE=1'], False),
    ('wasi_unavailable', ['-D__wasi__=1', '-DZERO_CLOCK=1'], False),
    ('wasi_zero_first', ['-D__wasi__=1', '-DZERO_FIRST=1'], False),
    ('wasi_other_clock', ['-D__wasi__=1', '-DOTHER_CLOCK=1'], False),
    ('wasi_seconds', ['-D__wasi__=1', '-DNO_MONOTONIC=1', '-DSECONDS_CLOCK=1'], False),
    ('wasi_ftime', ['-D__wasi__=1', '-DNO_MONOTONIC=1', '-DFTIME_CLOCK=1'], False),
]


def compare(before, after, skipped):
    # Clocks are deterministic: every metadata field must still match, including
    # zero metadata on unavailable / initial-zero reads. Real resolution policy
    # is nominal1, not a promise that arbitrary host scheduling has 1ms steps.
    assert before['timers'] == after['timers'], (before, after)
    if skipped:
        assert before['milliseconds_calls'] == 1001
        assert after['milliseconds_calls'] == 21
        assert after['timers']['milliseconds'][2:] == [1000, 1]
    else:
        assert before == after, (before, after)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    pins, source, original = prepare_inputs(args.work)
    before = original['mysys/my_rdtsc.c']
    after = (source/'mysys/my_rdtsc.c').read_text()
    # Ensure there is exactly one added conditional branch; all other bytes,
    # including real clocks, discovery and frequency calibration, are unchanged.
    block = after[after.index('#if defined(__wasi__)'):after.index('#endif',after.index('#if defined(__wasi__)'))+len('#endif\n')]
    assert after.replace(block,'',1) == before
    header = original['include/my_rdtsc.h']
    types = header[header.index('struct my_timer_unit_info'):header.index('typedef struct my_timer_info MY_TIMER_INFO;')+len('typedef struct my_timer_info MY_TIMER_INFO;')]
    routines = '\n'.join(re.findall(r'(?m)^#define MY_TIMER_ROUTINE_\w+\s+\d+\s*$',header))
    signatures = ['static void my_timer_init_overhead(', 'static ulonglong my_timer_init_resolution(',
                  'static ulonglong my_timer_init_frequency(', 'void my_timer_init(']
    def fixture(source):
        body = '\n'.join(function(source,sig) for sig in signatures)
        return FIXTURE.replace('@TYPES@',types).replace('@ROUTINES@',routines).replace('@FUNCTIONS@',body)
    compiler = os.environ.get('CXX','c++')
    version = subprocess.check_output([compiler,'--version'],text=True).splitlines()[0]
    def run(source, flags, name):
        text = fixture(source)
        cpp = args.work/(name+'.cc'); binary = cpp.with_suffix('')
        cpp.write_text(text)
        subprocess.run([compiler,'-std=c++17','-O2','-Wall','-Wextra','-Werror',*flags,str(cpp),'-o',str(binary)],check=True)
        result = subprocess.run([str(binary)],text=True,capture_output=True,check=True,timeout=10)
        return json.loads(result.stdout)
    cases = []; baseline = {}
    for name,flags,skip in PROFILES:
        b = run(before,flags,name+'-before'); a = run(after,flags,name+'-after')
        compare(b,a,skip); baseline[name] = b
        cases.append(dict(profile=name,probe_skipped=skip,before=b,after=a))
    controls = []
    mutations = [
        ('cycle_guard','wasi_cycles',after.replace('!mti->cycles.routine &&','1 &&',1)),
        ('pfs_guard','wasi_pfs',after.replace('!defined(HAVE_PSI_INTERFACE)','1',1)),
        ('native_guard','native_no_cycles',after.replace('defined(__wasi__)','1',1)),
        ('frequency','wasi_no_cycles',after.replace('mti->milliseconds.resolution= 1;', 'mti->milliseconds.resolution= 1, mti->milliseconds.frequency= 1001;',1)),
    ]
    for name,profile,source in mutations:
        _,flags,skip = next(p for p in PROFILES if p[0]==profile)
        changed = run(source,flags,'mutation-'+name)
        try: compare(baseline[profile],changed,skip)
        except AssertionError: pass
        else: raise AssertionError('mutation was not detected: '+name)
        controls.append(dict(mutation=name,detected=True))
    result = dict(result='INITIALIZER_UNIT_PASS',compiler=version,
                  mariadb_source_commit=pins['mariadb_source_commit'],
                  source_before_sha256=sha(before.encode()),source_after_sha256=sha(after.encode()),
                  patch_sha256=sha((ROOT/'guest/source.patch').read_bytes()),
                  cases=cases,negative_controls=controls,
                  limitation='Controlled clocks, exact C initializer; no actual-guest timing or performance claim.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['result'])


if __name__ == '__main__':
    main()
