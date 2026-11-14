"""Adapt native OS failures to the existing guest-visible WASI contract."""

CHANGES = (
    ('func mapOSError(err error) int32 {\n\tif err == nil {',
     'func mapOSError(err error) int32 {\n\terr = normalizeNativeError(err)\n\tif err == nil {'),
    ('if _, err := op.f.Write(nil); err != nil {',
     'if err := nativeFileWriteProbe(op.f); err != nil {'),
)


def apply(name, text):
    if name != 'code/base/base.go':
        return text
    for old, new in CHANGES:
        if text.count(old) != 1:
            raise ValueError('native OS error adapter preimage changed: ' + old)
        text = text.replace(old, new, 1)
    return text
