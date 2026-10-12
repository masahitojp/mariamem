"""Platform-bound production lowering; fail closed on converter shape changes.

The pinned generic converter keeps its portable CAS implementation. This
installer owns mariamem's two supported native exact-width load primitives;
all stores/RMW/cmpxchg remain unchanged and retain their documented limits.
"""
def apply(text):
    for bits,width in [(8,1),(16,2)]:
        old=(f'return int32(AtomicSubword32(m, AtomicEA(m, addr, offset, {width}), {bits}, '
             'func(old uint32) uint32 { return old }))')
        new=f'return int32(atomicRead{bits}At(unsafe.Add(m.M, uintptr(AtomicEA(m, addr, offset, {width})))))'
        if text.count(old)!=1:raise ValueError('narrow atomic converter shape changed: '+str(bits))
        text=text.replace(old,new,1)
    return text
