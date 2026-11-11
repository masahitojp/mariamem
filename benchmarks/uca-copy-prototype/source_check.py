"""Bounded native UCA producer oracle with explicit WASM32 scalar layout.

Inputs are pinned upstream files in --source; all builds go under --out.
This is not a MariaDB server, generated guest or SQL acceptance test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import struct
import os
from failure_fix import apply as fix_failure


def sha(data):
    return hashlib.sha256(data).hexdigest()


def between(text, begin, end):
    assert text.count(begin) == 1 and text.count(end) == 1
    return text[text.index(begin):text.index(end)]


def function(text, name):
    match = re.search(r'(?m)^' + name + r'\([^;{}]*\)\s*\{', text)
    assert match, name
    start = text.rfind('\n', 0, match.start() - 1) + 1
    end = text.index('\n}', match.end()) + 2
    return text[start:end] + '\n'


def run(args, *, stdout=None):
    subprocess.run(args, check=True, timeout=120, stdout=stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    src, out = args.source.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    pins = json.loads((here / 'inputs.json').read_text())
    for name, digest in pins['sha256'].items():
        assert sha((src / name).read_bytes()) == digest, name
    header = (src / 'm_ctype.h').read_text()
    base = '''#pragma once
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <strings.h>
typedef uint32_t uint;
typedef uint16_t uint16;
typedef unsigned char uchar;
typedef char my_bool;
typedef uint32_t my_wc_t;
#define TRUE 1
#define FALSE 0
#define array_elements(x) (sizeof(x)/sizeof((x)[0]))
#define DBUG_ASSERT(x) assert(x)
#define PRAGMA_DISABLE_CHECK_STACK_FRAME
#define PRAGMA_REENABLE_CHECK_STACK_FRAME
typedef struct { const char *str; size_t length; } LEX_CSTRING;
#define STRING_WITH_LEN(x) x, sizeof(x)-1
#define set_if_smaller(a,b) do { if ((a) > (b)) (a) = (b); } while (0)
'''
    (out / 'my_global.h').write_text(base)
    structs = between(header, '#define MY_UCA_MAX_CONTRACTION', 'my_bool my_uca_can_be_contraction_head')
    hash_type = between(header, 'typedef struct my_uca_contraction_hash_t', '/* Collation weights on a single level')
    (out / 'm_ctype.h').write_text('#pragma once\n#include "my_global.h"\n' + structs + hash_type)
    h = (src / 'ctype-uca.h').read_text()
    h14 = (src / 'ctype-uca1400.h').read_text()
    # Only declarations irrelevant to the standalone generator are excluded.
    # All implicit-weight function bodies are exact upstream substrings.
    implicit = between(h, '#define MY_UCA_VERSION_ID', 'typedef enum my_cs_encoding_enum')
    implicit += h14[h14.index('/*\n  17000'):h14.index('#define MY_UCA1400_COLLATION_ID_POSSIBLE_MIN')]
    implicit += h[h.index('static inline MY_UCA_IMPLICIT_WEIGHT\nmy_uca_implicit_weight_primary(uint'):h.index('uint\nmy_ci_get_id_uca')]
    (out / 'ctype-uca.h').write_text('#pragma once\n' + implicit)
    # Place unchanged source beside the minimal dependency headers.
    (out / 'uca-dump.c').write_bytes((src / 'uca-dump.c').read_bytes())
    run(['cc', '-std=c11', '-O2', '-I', str(out), str(out / 'uca-dump.c'), '-o', str(out / 'uca-dump')])
    with (out / 'ctype-uca1400data.h').open('wb') as stream:
        run([str(out / 'uca-dump'), '--name-prefix=uca1400', '--levels=3', str(src / 'allkeys1400.txt')], stdout=stream)
    print('Pinned original uca-dump PASS', flush=True)

    data = (out / 'ctype-uca1400data.h').read_text()
    source_c = (src / 'ctype-uca.c').read_text()
    arrays, entries, expected, hash_rows, flag_rows = [], [], [], [], []
    for suffix in ['', '_secondary', '_tertiary']:
        name = 'uca1400_contractions' + suffix
        match = re.search(r'static MY_CONTRACTION ' + name + r'\[939\]=\{\n(.*?)\n\};', data, re.S)
        assert match, name
        arrays.append(match[0])
        rows = []
        for line in match[1].splitlines():
            row = re.fullmatch(r'\{\{([^}]+)\}, \{([^}]+)\}, (FALSE|TRUE)\},?', line)
            assert row, line
            ch = [int(x.strip(), 0) for x in row[1].split(',') if x.strip()]
            weights = [int(x.strip(), 0) for x in row[2].split(',') if x.strip()]
            assert len(ch) <= 6 and len(weights) <= 17
            rows.append((ch + [0]*(6-len(ch)), weights + [0]*(17-len(weights)), int(row[3]=='TRUE')))
        assert len(rows) == 939
        entries.append(rows)
        flags = bytearray(4096)
        table = [None]*4096
        for ch, weights, context in rows:
            length = ch.index(0) if 0 in ch else 6
            assert 2 <= length <= 6
            flags[ch[0] & 4095] |= 64 if context else 1
            for index in range(1, length-1):
                flags[ch[index] & 4095] |= 1 << (index+1)
            flags[ch[length-1] & 4095] |= 128 if context else 2
            pos = ((ch[0]*465 + ch[1]) & 1023) << 2
            attempts = 0
            while table[pos] is not None:
                pos = (pos+1) % 4096
                attempts += 1
                assert attempts < 4095
            table[pos] = (ch, weights, context)
        def packed(row):
            return struct.pack('<6I17HBx', *row[0], *row[1], row[2]) if row else bytes(60)
        expected.append(b''.join(map(packed, rows)) + flags + b''.join(map(packed, table)))
        hash_rows.append(table)
        flag_rows.append(flags)
    (out / 'contractions.h').write_text('\n'.join(arrays))
    def initializer(row):
        ch,w,c = row
        return '{{' + ','.join(map(str,ch)) + '},{' + ','.join(map(str,w)) + '},' + str(c) + '}'
    generated = ['/* Generated from pinned Unicode1400 input; no pointers. */',
                 '_Static_assert(sizeof(my_wc_t)==4 && sizeof(uint16)==2 && sizeof(my_bool)==1, "scalar layout");',
                 '_Static_assert(sizeof(MY_CONTRACTION)==60 && offsetof(MY_CONTRACTION, weight)==24 && offsetof(MY_CONTRACTION, with_context)==58, "contraction layout");',
                 'static const unsigned char mariamem_uca_copy_flags[3][4096]={']
    for flags in flag_rows:
        generated.append('{' + ','.join(f'[{i}]={x}' for i,x in enumerate(flags) if x) + '},')
    generated += ['};', 'static const MY_CONTRACTION mariamem_uca_copy_hash[3][4096]={']
    for table in hash_rows:
        generated.append('{')
        generated.extend(f'[{i}]={initializer(row)},' for i,row in enumerate(table) if row)
        generated.append('},')
    generated.append('};\n')
    (out / 'prepared.h').write_text('\n'.join(generated))
    names = ['my_wstrnlen', 'my_uca_add_contraction_flag', 'my_uca_add_contraction',
             'my_uca_alloc_contractions', 'my_uca_init_one_contraction',
             'my_uca_contraction_hash_func', 'my_uca_contraction_hash_find_empty',
             'my_uca_contraction_hash_allocate', 'my_uca_contraction_hash_populate']
    definitions = [function(source_c, n) for n in names]
    constants = between(source_c, '#define MY_UCA_CONTRACTION_HASH_ALLOC_ELEMENTS', '/*#define DBUG_UCA_CONTRACTIONS*/')
    start = source_c.rindex('#define MY_UCA_CNT_FLAG_SIZE')
    constants += source_c[start:source_c.index('static inline uint16', start)]
    (out / 'reference.h').write_text(constants + '\n'.join(definitions))
    harness = (here / 'harness.c').read_text()
    (out / 'harness.c').write_text(harness)
    (out / 'copy.c').write_text((here / 'copy.c').read_text())
    run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(out), str(out/'harness.c'), '-o', str(out/'harness')])
    with (out/'original.bin').open('wb') as stream:
        run([str(out/'harness')], stdout=stream)
    assert (out/'original.bin').read_bytes() == b''.join(expected), 'original producer differs from prepared Python output'
    # Verify the exact helper's independent original-producer mode, not profiling.
    verified = subprocess.run([str(out/'harness')], check=True, timeout=120,
                              env=dict(os.environ, MARIAMEM_UCA_COPY_VERIFY_INTERNAL='1'),
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    assert verified.stderr.count('UCA_COPY_VERIFY id=') == 15
    original_header = (out/'prepared.h').read_text()
    mutants = {
        'flags': re.sub(r'\[([0-9]+)\]=([0-9]+)', lambda m: '['+m[1]+']='+str(int(m[2]) ^ 1), original_header, count=1),
        'hash': re.sub(r'(\[[0-9]+\]=\{\{)([0-9]+)', lambda m: m[1]+str(int(m[2]) ^ 1), original_header, count=1),
        'layout': original_header.replace('sizeof(MY_CONTRACTION)==60', 'sizeof(MY_CONTRACTION)==61'),
    }
    for name, mutant in mutants.items():
        assert mutant != original_header
        (out/'prepared.h').write_text(mutant)
        compiled = subprocess.run(['cc', '-std=c11', '-O2', '-I', str(out), str(out/'harness.c'), '-o', str(out/'mutant')],
                                  timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if name == 'layout':
            assert compiled.returncode != 0 and b'contraction layout' in compiled.stderr
        else:
            assert compiled.returncode == 0, compiled.stderr
            rejected = subprocess.run([str(out/'mutant')], timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            assert rejected.returncode == 2 and b'CHECK failed:' in rejected.stderr
    (out/'prepared.h').write_text(original_header)

    caller_names = ['my_uca1400_collation_get_initialized_shared_uca', 'create_tailoring']
    (out/'caller.c').write_text((here/'caller.c').read_text())
    for label, code in [('original', source_c), ('fixed', fix_failure(source_c))]:
        (out/'caller-functions.h').write_text('\n'.join(function(code,n) for n in caller_names))
        command = ['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(out),str(out/'caller.c'),'-o',str(out/'caller')]
        if label == 'original':
            command.insert(1,'-DEXPECT_ORIGINAL_BUG')
        run(command)
        run([str(out/'caller')])
    check = {'result':'PASS_SOURCE_ONLY', 'native_sql':False, 'guest_execution':False,
             'caller_failure_original':'false-success and skipped retry reproduced in exact callers with stubbed initializer',
             'caller_failure_fixed':'error propagated and fresh retry on default and alias routes',
             'failure_fix_sha256':sha((here/'failure_fix.py').read_bytes()),
             'implementation_sha256':{n:sha((here/n).read_bytes()) for n in ['copy.c','harness.c','caller.c','failure_fix.py','source_check.py']},
             'negative_controls':['flags corruption','hash corruption','layout mismatch'],
             'profile_level_copies':15, 'allocation_failure_points':3, 'guard_misses':9,
             'verification_mode_original_comparisons':15, 'ownership_mutations':3,
             'levels':3, 'items_per_level':939, 'full_original_bytes_compared':len(b''.join(expected)),
             'prepared_numeric_bytes':749568, 'prepared_header_sha256':sha((out/'prepared.h').read_bytes()),
             'generated_unicode_header_sha256':sha((out/'ctype-uca1400data.h').read_bytes()),
             'original_payload_sha256':sha((out/'original.bin').read_bytes()),
             'original_functions_sha256':{n:sha(d.encode()) for n,d in zip(names,definitions)},
             'original_body_modification':False,
             'scalar_abi':'native harness explicitly models WASM32 my_wc_t=uint32 and 60-byte contraction; real guest still required'}
    (out/'result.json').write_text(json.dumps(check,indent=2)+'\n')
    print('Original producer / independent prepared bytes / private-copy harness PASS', flush=True)


if __name__ == '__main__':
    main()
