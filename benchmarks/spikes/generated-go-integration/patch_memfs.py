"""Pinned generator-output adaptation: stable nodes and an injectable opener.

The installer checks the entire unpatched base digest before calling this.
Every replacement is exact and fails closed if the generator layout changes.
"""

def apply(text):
    def change(old, new):
        nonlocal text
        count = text.count(old)
        if count != 1:
            raise ValueError(f"expected one generator fragment, found {count}: {old[:80]!r}")
        text = text.replace(old, new, 1)

    change('type memNode struct {\n', 'type memNode struct {\n\tparent *memNode // stable parent identity; retained after unlink\n')
    change('node = &memNode{name: base, mode: perm & 0o777, modTime: time.Now()}',
           'node = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now()}')
    change('parent.children[base] = &memNode{name: base, dir: true,',
           'parent.children[base] = &memNode{parent: parent, name: base, dir: true,')
    change('c = &memNode{name: part, dir: true,',
           'c = &memNode{parent: n, name: part, dir: true,')
    change('parent.children[base] = &memNode{name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}',
           'parent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}')
    change('delete(op.children, ob)\n\tnode.name = nb\n\tnp.children[nb] = node',
           '''// A directory cannot be moved into itself or a descendant.
	for p := np; p != nil; p = p.parent {
		if p == node { return &fs.PathError{Op: "rename", Path: oldName, Err: syscall.EINVAL} }
	}
	delete(op.children, ob)
	node.parent = np
	node.name = nb
	np.children[nb] = node''')
    change('''	fsys := w.fsys
	w.mu.Unlock()

	canRead := fsRightsBase&(1<<1) != 0''', '''	fsys := w.fsys
	w.mu.Unlock()
	return w.pathOpenOnFS(fsys, rel, rel, dirflags, oflags, fsRightsBase, fdflags)
}

// Resolution happens in the supplied opened directory, never via its pathname.
// policyPath is only the existing access-hook label, not a lookup operand.
func (w *WasiStubs) pathOpenOnFS(fsys relativeFileSystem, rel, policyPath string, dirflags, oflags int32, fsRightsBase int64, fdflags int32) (int32, int32) {
	canRead := fsRightsBase&(1<<1) != 0''')
    change('if !w.checkFS(rel, writeAccess) {', 'if !w.checkFS(policyPath, writeAccess) {')
    change('''func (w *WasiStubs) SetFS(fsys FS) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if fsys == nil {
		fsys = osFS{root: w.preopenDir}
	}
	w.fsys = fsys
}''', '''func (w *WasiStubs) SetFS(fsys FS) {
	// Materialize the preopen so close/dup/renumber obey the same FD identity
	// rules as every opened directory. SetFS is setup-only, before guest entry.
	if fsys == nil { fsys = osFS{root: w.preopenDir} }
	root, err := fsys.OpenFile(".", os.O_RDONLY, 0)
	if err != nil { panic(fmt.Sprintf("preopen root: %v", err)) }
	w.mu.Lock()
	previous := w.fdTable[3]
	w.fsys = fsys
	w.fdTable[3] = &wasiOpen{f: root, isDir: true, path: "/"}
	w.mu.Unlock()
	if previous != nil { _ = closeWasiOpen(previous) }
}''')
    # Logical length remains independent of reusable allocation capacity.
    # Clear newly exposed bytes even after truncate/O_TRUNC: stale data in
    # retained capacity (including a child's private mmap) is not file content.
    change('''		grown := make([]byte, end)
		copy(grown, f.node.data)
		f.node.data = grown''', '''		f.node.data = resizeMemData(f.node.data, end)''')
    change('''	if size <= int64(len(f.node.data)) {
		f.node.data = f.node.data[:size]
	} else {
		grown := make([]byte, size)
		copy(grown, f.node.data)
		f.node.data = grown
	}''', '''	f.node.data = resizeMemData(f.node.data, size)''')
    return text
