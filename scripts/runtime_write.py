"""Preserve zero-progress WASI write errors in the pinned runtime helper.

A successful partial write reports its byte count; a zero-byte failure must
return errno so libc cannot retry a broken pipe as successful no-progress I/O.
No translated MariaDB function is changed. Reject changed preimages.
"""

CHANGES = (
    ('''func writeVec(dst io.Writer, bufs [][]byte) uint64 {
	var total uint64
	for _, buf := range bufs {
		n, err := dst.Write(buf)
		total += uint64(n)
		if err != nil {
			break
		}
	}
	return total
}''',
     '''func writeVec(dst io.Writer, bufs [][]byte) (uint64, error) {
	var total uint64
	for _, buf := range bufs {
		n, err := dst.Write(buf)
		total += uint64(n)
		if err != nil {
			return total, err
		}
		if n < len(buf) {
			return total, io.ErrShortWrite
		}
	}
	return total, nil
}'''),
    ('''	binary.LittleEndian.PutUint32(nwrittenSlice, uint32(writeVec(dst, bufs)))
	return _wasiESUCCESS''',
     '''	n, err := writeVec(dst, bufs)
	binary.LittleEndian.PutUint32(nwrittenSlice, uint32(n))
	if err != nil && n == 0 {
		return mapOSError(err)
	}
	return _wasiESUCCESS'''),
    ('''	binary.LittleEndian.PutUint64(nwrittenSlice, writeVec(dst, bufs))
	return _wasiESUCCESS''',
     '''	n, err := writeVec(dst, bufs)
	binary.LittleEndian.PutUint64(nwrittenSlice, n)
	if err != nil && n == 0 {
		return mapOSError(err)
	}
	return _wasiESUCCESS'''),
)


def apply(name, text):
    if name != 'code/base/base.go':
        return text
    for old, new in CHANGES:
        if text.count(old) != 1:
            raise ValueError('WASI write runtime preimage changed: ' + repr(old))
        text = text.replace(old, new, 1)
    return text
