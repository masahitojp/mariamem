"""Bind the active and idle tpool periods for the audited embedded guest."""
import hashlib

GUEST = '869ffee51c519e4ef725bbc0c0049dd7f121e1070166ad43a5f356094891164a'
INPUTS = {
    'code/p3/p3_pure.go': '3ced860376addabc59a118238e33405202d1c28e6cecdfcdcd5725be91fc64d7',
    'code/p5/p5_pure.go': '95ca1fe099f1b12645a636f9eb81586b909b9918435e456d5a90f85834617d53',
}


def install(output, guest):
    if guest != GUEST:
        return
    changes = {}
    for name, digest in INPUTS.items():
        path = output / name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'unrecognized tpool generation input: {name}')
        source = data.decode()
        if name.startswith('code/p3/'):
            function = 'Fn16634'
            field = '*(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v13)), 216, 8)))'
            edits = [(field+' = int64(400)', field+' = int64(50)', 1)]
        else:
            function = 'Fn16626'
            # The two inlined idle paths update either a microsecond timer or
            # a millisecond pending period. Keep their bounds-checked loads.
            edits = [
                (' = v63 * int64(42949672960) >> (uint(int64(32)) % 64) * int64(1000)', ' = int64(4000000)', 2),
                (' = base.I32_wrap_i64(v63) * int32(10)', ' = int32(4000)', 2),
            ]
        start = source.index('func '+function+'(')
        end = source.index('\n}', start)
        body = source[start:end]
        for original, replacement, expected in edits:
            if body.count(original) != expected:
                raise ValueError(f'unrecognized timer assignment in {function}')
            body = body.replace(original, replacement)
        changes[path] = source[:start]+body+source[end:]
    for path, source in changes.items():
        path.write_text(source)
