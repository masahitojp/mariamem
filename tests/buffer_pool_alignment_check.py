"""Focused host-compiled checks of Issue63's exact prepared WASM allocator body.

This exercises the C contract, not WASIX allocator OOM or whole-guest behavior.
Pass a source tree after adopted portability + guest/experimental.patch.
Temporary compilation output is removed on success and failure.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess
import tempfile


def function(text, name):
    start = text.index('char *' + name + '(')
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define DBUG_ENTER(name) ((void)0)
#define DBUG_RETURN(value) return (value)
static int fail_alloc, calls;
static size_t last_alignment, last_size;
static void *allocation;
static int checked_memalign(void **p, size_t alignment, size_t bytes) {
  ++calls;
  last_alignment = alignment;
  last_size = bytes;
  if (fail_alloc) return ENOMEM;
  int result = posix_memalign(p, alignment, bytes);
  if (!result) {
    allocation = *p;
    /* Dirty the complete allocation so the zero contract is observable. */
    memset(*p, 0xa5, bytes);
  }
  return result;
}
#define posix_memalign checked_memalign
'''

ORACLES = r'''
static void check_one(size_t size, size_t alignment, int legacy) {
  size_t before = size;
  calls = 0;
  char *p = legacy ? my_large_virtual_alloc(&size) :
                    my_large_virtual_alloc_aligned(&size, alignment);
  assert(size == before && calls == 1);
  assert(last_size == before && last_alignment == alignment);
  if (fail_alloc) { assert(p == NULL); return; }
  assert(p && p == allocation && (uintptr_t)p % alignment == 0);
  for (size_t i = 0; i < size; ++i) assert(p[i] == 0);
  memset(p, 0x5a, size);
  free(p); /* The returned original pointer remains directly freeable. */
}
int main(void) {
  const size_t sizes[] = {1, 4095, 4096, 2097151, 2097152, 2097153, 16777216};
  for (unsigned i = 0; i < sizeof sizes / sizeof *sizes; ++i) {
    for (fail_alloc = 0; fail_alloc <= 1; ++fail_alloc) {
      check_one(sizes[i], 4096, 1);
      check_one(sizes[i], 2097152, 0);
    }
  }
  return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    names = ['mysys/my_largepage.c', 'include/my_sys.h',
             'storage/innobase/buf/buf0buf.cc', 'mysys/my_virtual_mem.c']
    sources = {name: (args.source / name).read_text() for name in names}
    large = sources[names[0]]
    helper = function(large, 'my_large_virtual_alloc_aligned')
    whole_legacy = function(large, 'my_large_virtual_alloc')
    wasm = re.search(r'#if defined\(__EMSCRIPTEN__\) \|\| defined\(__wasi__\)\n(.*?)#endif',
                     whole_legacy, re.S).group(1)
    legacy = 'char *my_large_virtual_alloc(size_t *size) {\n' + wasm + '\n}'
    declaration = 'char *my_large_virtual_alloc_aligned(size_t *size, size_t alignment);'
    assert '#if defined(__EMSCRIPTEN__) || defined(__wasi__)\n' + declaration in sources[names[1]]
    pool = sources[names[2]]
    assert pool.count('my_large_virtual_alloc_aligned(') == 1
    canonical_dispatch = re.search(r'#if defined\(__EMSCRIPTEN__\) \|\| defined\(__wasi__\)\n'
                     r'    memory_unaligned= my_large_virtual_alloc_aligned\(\n'
                     r'        &size, innodb_buffer_pool_extent_size\);\n#else\n'
                     r'    memory_unaligned= my_virtual_mem_reserve\(&size\);\n#endif', pool)
    if "MARIAMEM_BP_ZERO_MODE_INTERNAL" in pool:
        # Exact reviewed experiment input only; the common allocator contract
        # below is still compiled and its four semantic mutants must fail.
        assert hashlib.sha256(pool.encode()).hexdigest() == "e2c3250d5a360aa89cd00e21a9dea55ce13e8ad35ef6bd8cf083b3ad516251e1"
        assert "posix_memalign(&p, innodb_buffer_pool_extent_size, size)" in pool
        assert "memset((void*) block, 0, descriptor_bytes);" in pool
        assert "BP_ZERO_REJECT nonzero_descriptor" in pool
    else:
        assert canonical_dispatch
    assert 'return my_large_virtual_alloc(size);' in sources[names[3]]
    assert 'free(ptr);' in sources[names[3]]
    cc = ['cc', '-std=c11', '-D_POSIX_C_SOURCE=200112L', '-Wall', '-Wextra', '-Werror']
    results = []
    with tempfile.TemporaryDirectory(prefix='issue63-contract-') as temporary:
        temp = Path(temporary)
        source = temp / 'contract.c'
        source.write_text(PRELUDE + helper + '\n' + legacy + ORACLES)
        binary = temp / 'contract'
        subprocess.run(cc + [str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], cwd=temp, check=True)
        results.append('dirty-buffer zero-fill, exact alignment/size, legacy 4KiB, controlled ENOMEM, original-pointer free')
        # A C++ caller must bind the same symbol as the C implementation.
        implementation = temp / 'allocator.c'
        implementation.write_text('#include <stdlib.h>\n#include <string.h>\n'
                                  '#define DBUG_ENTER(x) ((void)0)\n#define DBUG_RETURN(x) return (x)\n' + helper)
        obj = temp / 'allocator.o'
        subprocess.run(cc + ['-c', str(implementation), '-o', str(obj)], check=True)
        caller = temp / 'caller.cc'
        caller.write_text('#include <stdlib.h>\nextern "C" {\n' + declaration + '\n}\n'
                          'int main() { size_t n=16777216; char *p=my_large_virtual_alloc_aligned(&n,2097152);'
                          'if (!p) return 1; free(p); return 0; }\n')
        linked = temp / 'caller'
        subprocess.run(['c++', '-Wall', '-Wextra', '-Werror', str(caller), str(obj), '-o', str(linked)], check=True)
        subprocess.run([str(linked)], cwd=temp, check=True)
        results.append('C implementation / C++ caller linkage')
        # Prove the contract checks catch meaningful regressions.
        mutations = {
            'missing-zero': (helper.replace('memset(p, 0, *size);', ''), legacy),
            'wrong-alignment': (helper.replace('posix_memalign(&p, alignment, *size)',
                                              'posix_memalign(&p, alignment + 4096, *size)'), legacy),
            'size-mutation': (helper.replace('memset(p, 0, *size);', 'memset(p, 0, *size); --*size;'), legacy),
            'legacy-alignment': (helper, legacy.replace('size, 4096', 'size, 2097152')),
        }
        for name, (changed, wrapper) in mutations.items():
            source.write_text(PRELUDE + changed + '\n' + wrapper + ORACLES)
            subprocess.run(cc + [str(source), '-o', str(binary)], check=True)
            run = subprocess.run([str(binary)], cwd=temp, capture_output=True)
            assert run.returncode != 0, 'oracle missed ' + name
        results.append('four semantic mutations rejected')
    record = {'result': 'PASS', 'scope': 'host C contract; not real WASIX OOM or guest execution',
              'checks': results, 'sources_sha256': {
                  n: hashlib.sha256((args.source / n).read_bytes()).hexdigest() for n in names},
              'compiler': subprocess.check_output(['cc', '--version'], text=True).splitlines()[0]}
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
