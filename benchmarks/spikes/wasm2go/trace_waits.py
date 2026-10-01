#!/usr/bin/env python3
"""Instrument an isolated generated module; buffer events, write only after exit."""
import argparse
from pathlib import Path


def replace(path, old, new):
    text = path.read_text()
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('module', type=Path)
    a = p.parse_args()
    assert (a.module/'go.mod').is_file(), 'nested module required'
    b = a.module/'generated/base/base.go'
    replace(b, 'return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)',
            'return m.Threads.wake(m, AtomicEA(m, addr, offset, 4), count)')
    replace(b, 'func (p *ThreadPool) wake(ea uint64, count int32) int32 {',
            'func (p *ThreadPool) wake(m *Module, ea uint64, count int32) int32 {')
    replace(b, '\tfor _, ch := range waiters[:n] {\n\t\tclose(ch)',
            '\tSpikeEvent(m,"notify",ea,int64(count),int64(n),0,0)\n\tfor _, ch := range waiters[:n] {\n\t\tSpikeEvent(m,"wake",ea,int64(count),int64(n),0,spikeToken(ch))\n\t\tclose(ch)')
    replace(b, 'func AtomicWait32At(m *Module, ea uint64, expected int32, timeout int64) int32 {\n\tp := AtomicPtr32At(m, ea)',
            'func AtomicWait32At(m *Module, ea uint64, expected int32, timeout int64) (rc int32) {\n\tp := AtomicPtr32At(m, ea)\n\tSpikeEvent(m,"wait",ea,int64(expected),int64(atomic.LoadUint32(p)),timeout,0)\n\tdefer func(){ SpikeEvent(m,"return",ea,int64(expected),int64(rc),timeout,0) }()')
    replace(b, '\tif !stillEqual() {\n\t\tm.Threads.parkMu.Unlock()',
            '\tif !stillEqual() {\n\t\tSpikeEvent(m,"mismatch",ea,0,0,timeout,0)\n\t\tm.Threads.parkMu.Unlock()')
    replace(b, '\tm.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\n\tm.Threads.parkMu.Unlock()',
            '\tm.Threads.parked[ea] = append(m.Threads.parked[ea], ch)\n\tSpikeEvent(m,"park",ea,0,0,timeout,spikeToken(ch))\n\tm.Threads.parkMu.Unlock()')
    replace(b, '\tcase <-timer.C:\n\t\tunpark()',
            '\tcase <-timer.C:\n\t\tSpikeEvent(m,"timeout",ea,0,0,timeout,spikeToken(ch))\n\t\tunpark()')
    replace(b, '\t*child = *m\n\tSpinAgentsAdd(1)',
            '\t*child = *m\n\tSpikeRegister(child,tid)\n\tSpikeEvent(m,"spawn",0,int64(tid),0,0,0)\n\tSpinAgentsAdd(1)')
    replace(b, '\tgo func() {\n\t\tdefer m.Threads.wg.Done()',
            '\tgo func() {\n\t\tSpikeEvent(child,"thread-start",0,int64(tid),0,0,0)\n\t\tdefer SpikeEvent(child,"thread-exit",0,int64(tid),0,0,0)\n\t\tdefer m.Threads.wg.Done()')
    (a.module/'generated/base/spike_trace.go').write_text((Path(__file__).with_name('wait-trace.go.txt')).read_text())
    replace(a.module/'main.go', 'func main() {', 'func main() {\n    defer base.SpikeDump()')
    replace(a.module/'main.go', '    trace("SPIKE start_begin")',
            '    base.SpikeEvent(m,"guest-start",0,0,0,0,0)\n    trace("SPIKE start_begin")')
    replace(a.module/'main.go', '    trace("SPIKE start_returned")',
            '    base.SpikeEvent(m,"guest-return",0,0,0,0,0)\n    trace("SPIKE start_returned")')
    # This artifact's symbol map identifies Fn18163 as buf_flush_page_cleaner.
    # Observe the target read before and after its contended mutex acquisition.
    pg = a.module/'generated/p2/p2_pure.go'
    old='\tv94 = int64(atomic.LoadUint64((*uint64)(unsafe.Add(mBase, _consts[1320]))))'
    replace(pg,old,old+'\n\tbase.SpikeEvent(m,"cleaner-target-before-lock",uint64(_consts[1320]),v94,0,0,0)')
    old='\tv100 = Fn94(m, int32(6880064))\n\tmBase = m.M'
    replace(pg,old,old+'\n\tbase.SpikeEvent(m,"cleaner-target-after-lock",uint64(_consts[1320]),v94,int64(atomic.LoadUint64((*uint64)(unsafe.Add(mBase,_consts[1320])))),0,0)')
    pg = a.module/'generated/p6/p6_pure.go'
    old='func Fn220(m *base.Module, l0 int32, l1 int32) int32 {'
    replace(pg,old,old+'\n\tbase.SpikeEvent(m,"cond-signal",uint64(uint32(l0)),int64(*(*uint32)(unsafe.Add(m.M,uint32(l0)+20))),int64(l1),0,0)')


if __name__ == '__main__': main()
