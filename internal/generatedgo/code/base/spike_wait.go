package base

func SpikeWait(m *Module) {
	if p := m.Threads.WaitThreads(); p != nil {
		panic(p)
	}
}
