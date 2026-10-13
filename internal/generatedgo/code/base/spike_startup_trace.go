package base

// Experiment-only startup ordering trace. This file is not a product change.
import (
	"encoding/json"
	"os"
	"sync"
	"time"
	"unsafe"
)

type SpikeStartupEvent struct {
	Seq      int    `json:"seq"`
	NS       int64  `json:"ns"`
	Kind     string `json:"kind"`
	Instance uint64 `json:"instance"`
	Agent    uint64 `json:"agent"`
	EA       uint64 `json:"ea,omitempty"`
	A        int64  `json:"a,omitempty"`
	B        int64  `json:"b,omitempty"`
	C        int64  `json:"c,omitempty"`
}

var spikeStartupPath = os.Getenv("MARIAMEM_SPIKE_TRACE")
var spikeStartup = struct {
	sync.Mutex
	start   time.Time
	events  []SpikeStartupEvent
	dropped int
}{start: time.Now(), events: make([]SpikeStartupEvent, 0, 50000)}

func SpikeStartup(m *Module, kind string, ea uint64, a, b, c int64) {
	if spikeStartupPath == "" {
		return
	}
	spikeStartup.Lock()
	defer spikeStartup.Unlock()
	if len(spikeStartup.events) == cap(spikeStartup.events) {
		spikeStartup.dropped++
		return
	}
	spikeStartup.events = append(spikeStartup.events, SpikeStartupEvent{
		Seq: len(spikeStartup.events), NS: time.Since(spikeStartup.start).Nanoseconds(),
		Kind: kind, Instance: uint64(uintptr(unsafe.Pointer(m.Threads))),
		Agent: uint64(uintptr(unsafe.Pointer(m))), EA: ea, A: a, B: b, C: c,
	})
}

func SpikeStartupDump() {
	if spikeStartupPath == "" {
		return
	}
	spikeStartup.Lock()
	defer spikeStartup.Unlock()
	data, err := json.MarshalIndent(struct {
		Events  []SpikeStartupEvent `json:"events"`
		Dropped int                 `json:"dropped"`
	}{spikeStartup.events, spikeStartup.dropped}, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(spikeStartupPath, append(data, '\n'), 0600); err != nil {
		panic(err)
	}
}
