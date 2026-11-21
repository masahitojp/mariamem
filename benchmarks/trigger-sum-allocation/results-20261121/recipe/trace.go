package pageprobe

import (
	"bytes"
	"encoding/json"
	"os"
	"sync/atomic"
	"unsafe"
)

type Frame struct {
	Trigger, Plan, Possible bool
	Arena                   int32
	SameArena               bool
	Key, Site               string
	Root, My, Wrap, DL      int32
}
type Event struct {
	Kind string
	Frame
	Guest, HostPage, InPage uint64
	Measurement
}
type Request struct {
	DB, Ordinal, SQL int
	Frame            Frame `json:"-"`
	Events           []Event
}

var active atomic.Pointer[Request]
var requests []*Request
var controls Controls

func Start() { controls = Calibrate() }
func Begin(db, ordinal int) {
	r := &Request{DB: db, Ordinal: ordinal}
	if active.Swap(r) != nil {
		panic("overlap")
	}
	requests = append(requests, r)
}
func Enter() *Request {
	r := active.Load()
	if r == nil || r.SQL != 0 {
		panic("SQL association")
	}
	r.SQL++
	return r
}
func Reply() {
	r := active.Swap(nil)
	if r == nil || r.SQL != 1 || r.Frame != (Frame{}) {
		panic("request attribution")
	}
}
func CString(mem []byte, off int32) string {
	b := mem[uint32(off):]
	n := bytes.IndexByte(b[:min(len(b), 128)], 0)
	if n < 0 {
		panic("unexpected index name")
	}
	return string(b[:n])
}
func (r *Request) Mark(kind string) {
	r.Events = append(r.Events, Event{Kind: kind, Frame: r.Frame})
}
func (r *Request) Store(base unsafe.Pointer, offset uint64, value int32) {
	addr := unsafe.Add(base, offset)
	query := 0
	if r.DB == 0 || r.DB == 3 || r.DB == 5 || r.DB == 6 {
		query = 1
	}
	m := Measure(addr, value, 1, query)
	size := uintptr(controls.PageSize)
	r.Events = append(r.Events, Event{Kind: "store", Frame: r.Frame, Guest: offset,
		HostPage: uint64(uintptr(addr)/size - uintptr(base)/size), InPage: uint64(uintptr(addr) % size), Measurement: m})
}
func Save() {
	f, err := os.Create(os.Getenv("TRACE_OUTPUT"))
	check(err)
	check(json.NewEncoder(f).Encode(struct {
		Controls Controls
		Requests []*Request
	}{controls, requests}))
	check(f.Close())
}
