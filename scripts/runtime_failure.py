"""Bind worker failure notification and cooperative wait cancellation.

These exact runtime-helper edits do not alter translated guest function bodies.
Reject changed preimages rather than silently installing a partial failure path.
"""


def apply(name, text):
    if name != 'code/base/base.go':
        return text
    changes = (
        ('\ttrap   any\n', '\ttrap   any\n\tfailure *workerFailure\n'),
        ('''\t\t\t\tm.Threads.trapMu.Lock()
\t\t\t\tif m.Threads.trap == nil {
\t\t\t\t\tm.Threads.trap = r
\t\t\t\t}
\t\t\t\tm.Threads.trapMu.Unlock()''', '\t\t\t\tm.Threads.recordTrap(r)'),
        ('func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {\n',
         'func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {\n\tm.Threads.trapIfFailed()\n'),
        ('\tif timeout < 0 {\n\t\tif m.Threads.nextTID.Load() == 0 {',
         '\tdefer unpark()\n\tif timeout < 0 {\n\t\tif m.Threads.nextTID.Load() == 0 {'),
        ('\t\t<-ch\n\t\treturn 0\n', '''\t\tselect {
\t\tcase <-ch:
\t\tcase <-m.Threads.failureDone():
\t\t}
\t\tm.Threads.trapIfFailed()
\t\treturn 0
'''),
        ('\tcase <-ch:\n\t\treturn 0\n\tcase <-timer.C:',
         '\tcase <-m.Threads.failureDone():\n\t\tm.Threads.trapIfFailed()\n\t\tpanic("unreachable worker failure")\n\tcase <-ch:\n\t\tm.Threads.trapIfFailed()\n\t\treturn 0\n\tcase <-timer.C:'),
        ('\t\tbody(child, tid)\n', '\t\tm.Threads.trapIfFailed()\n\t\tbody(child, tid)\n'),
    )
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('worker failure runtime preimage changed: ' + repr(old))
        text = text.replace(old, new, 1)
    return text
