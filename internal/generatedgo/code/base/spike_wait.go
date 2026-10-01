package base

func SpikeWait(m *Module) { m.Threads.wg.Wait() }
