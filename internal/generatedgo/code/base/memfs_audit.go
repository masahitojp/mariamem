// Experiment-only bounded MemFS attribution. Installed by instrument.py.
package base

import (
	"encoding/json"
	"fmt"
	"math/bits"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
	"unsafe"
)

const auditPage = 4096
const auditMaxBytes = 1 << 30

var auditEnabled = os.Getenv("MARIAMEM_MEMFS_AUDIT") == "1"
var auditTimer = os.Getenv("MARIAMEM_MEMFS_RESIZE_TIMER") == "1"
var auditEvents = os.Getenv("MARIAMEM_MEMFS_GROWTH_EVENTS") == "1"

type AuditStats struct {
	Calls           uint64 `json:"calls"`
	InitialCount    uint64 `json:"initial_count"`
	ReallocCount    uint64 `json:"realloc_count"`
	InitialCapacity uint64 `json:"initial_capacity_bytes"`
	ReallocCapacity uint64 `json:"realloc_capacity_bytes"`
	OldCopied       uint64 `json:"old_logical_copied_bytes"`
	InputCopied     uint64 `json:"host_population_copied_bytes"`
	Cleared         uint64 `json:"explicit_clear_bytes"`
	DetachCount     uint64 `json:"mapped_detach_count"`
	Detached        uint64 `json:"mapped_detach_copied_bytes"`
	Read            uint64 `json:"read_bytes"`
	Write           uint64 `json:"write_bytes"`
	RequestedEOF    uint64 `json:"max_requested_eof"`
	ResizeNS        uint64 `json:"resize_ns"`
}
type AuditNode struct {
	ID            uint64                 `json:"id"`
	FS            uint64                 `json:"fs"`
	Path          string                 `json:"path"`
	Role          string                 `json:"role"`
	Epoch         uint64                 `json:"epoch"`
	Len           int                    `json:"logical_bytes"`
	Cap           int                    `json:"capacity_bytes"`
	MaxLen        int                    `json:"max_logical_bytes"`
	MaxCap        int                    `json:"max_capacity_bytes"`
	Mapped        bool                   `json:"mapped"`
	Imported      int                    `json:"imported_bytes"`
	Linked        bool                   `json:"linked"`
	Handles       int                    `json:"open_handles"`
	Ended         bool                   `json:"fs_ended"`
	Overflow      bool                   `json:"coverage_limit_exceeded"`
	Phases        map[string]*AuditStats `json:"phase_operation_stats"`
	touched, full []uint64
}
type AuditPoint struct {
	ID           uint64 `json:"id"`
	FS           uint64 `json:"fs"`
	Path         string `json:"path"`
	Role         string `json:"role"`
	Epoch        uint64 `json:"epoch"`
	Len          int    `json:"logical_bytes"`
	Cap          int    `json:"capacity_bytes"`
	Mapped       bool   `json:"mapped"`
	Imported     int    `json:"imported_bytes"`
	Linked       bool   `json:"linked"`
	Handles      int    `json:"open_handles"`
	Ended        bool   `json:"fs_ended"`
	Overflow     bool   `json:"coverage_limit_exceeded"`
	WrittenLower int    `json:"written_lower_bytes"`
	WrittenUpper int    `json:"written_upper_bytes"`
}
type AuditFrame struct {
	Phase             string          `json:"phase"`
	Nodes             []AuditPoint    `json:"nodes"`
	HeapAlloc         uint64          `json:"heap_alloc_bytes"`
	HeapInuse         uint64          `json:"heap_inuse_bytes"`
	TotalAlloc        uint64          `json:"total_alloc_bytes"`
	GC                uint32          `json:"num_gc"`
	ObserverAccounted uint64          `json:"observer_accounted_bytes"`
	ObserverBitmap    uint64          `json:"observer_bitmap_bytes"`
	Process           json.RawMessage `json:"process_counters,omitempty"`
	ProcessError      string          `json:"process_error,omitempty"`
}

var auditState = struct {
	sync.Mutex
	phase     string
	nextFS    uint64
	nodes     []*AuditNode
	frames    []AuditFrame
	accounted uint64
	bitmap    uint64
}{phase: "host-init"}

func AuditPhase(phase string) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	auditState.phase = phase
	auditState.Unlock()
}
func (fs *MemFS) AuditRole(role string) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	auditState.nextFS++
	fs.auditID = auditState.nextFS
	fs.auditRole = role
}
func auditPath(n *memNode) string {
	var p []string
	for n != nil && n.parent != nil {
		p = append(p, n.name)
		n = n.parent
	}
	for i, j := 0, len(p)-1; i < j; i, j = i+1, j-1 {
		p[i], p[j] = p[j], p[i]
	}
	return strings.Join(p, "/")
}

// Caller holds the existing FS lock and auditState, in that order.
func auditNode(fs *MemFS, n *memNode) *AuditNode {
	if n.audit == nil {
		n.audit = &AuditNode{ID: uint64(len(auditState.nodes) + 1), FS: fs.auditID, Path: auditPath(n), Role: fs.auditRole, Linked: true, Phases: map[string]*AuditStats{}}
		auditState.nodes = append(auditState.nodes, n.audit)
		auditState.accounted += uint64(unsafe.Sizeof(AuditNode{})) + uint64(len(n.audit.Path))
	}
	a := n.audit
	a.Len = len(n.data)
	a.Cap = cap(n.data)
	if a.Len > a.MaxLen {
		a.MaxLen = a.Len
	}
	if a.Cap > a.MaxCap {
		a.MaxCap = a.Cap
	}
	return a
}
func auditStats(a *AuditNode, op string) *AuditStats {
	key := auditState.phase + ":" + op
	s := a.Phases[key]
	if s == nil {
		s = &AuditStats{}
		a.Phases[key] = s
		auditState.accounted += uint64(unsafe.Sizeof(AuditStats{})) + uint64(len(key))
	}
	return s
}
func (fs *MemFS) auditOpen(n *memNode) {
	if !auditEnabled || n.dir {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	auditNode(fs, n).Handles++
}
func (f *memFile) auditClose() {
	if !auditEnabled {
		return
	}
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	if !f.auditClosed && !f.node.dir {
		auditState.Lock()
		auditNode(f.fsys, f.node).Handles--
		auditState.Unlock()
		f.auditClosed = true
	}
}
func (fs *MemFS) auditUnlink(n *memNode) {
	if !auditEnabled || n.dir {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	auditNode(fs, n).Linked = false
}
func (fs *MemFS) auditRename(n *memNode) {
	if !auditEnabled || n.dir {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	auditNode(fs, n).Path = auditPath(n)
}
func auditCoverage(a *AuditNode, off, n int) {
	if n <= 0 {
		return
	}
	end := off + n
	if off < 0 || end > auditMaxBytes {
		a.Overflow = true
		return
	}
	words := (end/auditPage+63)/64 + 1
	if words > len(a.touched) {
		old := len(a.touched)
		capacity := words * 2
		for _, dest := range []*[]uint64{&a.touched, &a.full} {
			b := make([]uint64, capacity)
			copy(b, *dest)
			*dest = b
		}
		auditState.bitmap += uint64(capacity-old) * 16
		auditState.accounted += uint64(capacity) * 16
	}
	for page := off / auditPage; page <= (end-1)/auditPage; page++ {
		a.touched[page/64] |= uint64(1) << uint(page%64)
		if off <= page*auditPage && end >= (page+1)*auditPage {
			a.full[page/64] |= uint64(1) << uint(page%64)
		}
	}
}
func auditShrink(a *AuditNode, size int) {
	a.Epoch++
	for i := range a.touched {
		start := i * 64 * auditPage
		if start >= size {
			a.touched[i] = 0
			a.full[i] = 0
			continue
		}
		if start+64*auditPage > size {
			pages := (size - start + auditPage - 1) / auditPage
			mask := ^uint64(0)
			if pages < 64 {
				mask = (uint64(1) << uint(pages)) - 1
			}
			a.touched[i] &= mask
			a.full[i] &= mask
			if size%auditPage != 0 {
				last := (size - 1) / auditPage
				a.full[last/64] &= ^(uint64(1) << uint(last%64))
			}
		}
	}
}
func (fs *MemFS) auditResize(n *memNode, size int64, op string) {
	if !auditEnabled {
		n.data = resizeMemData(n.data, size)
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	s := auditStats(a, op)
	s.Calls++
	if size >= 0 && uint64(size) > s.RequestedEOF {
		s.RequestedEOF = uint64(size)
	}
	oldLen, oldCap := len(n.data), cap(n.data)
	var start time.Time
	if auditTimer {
		start = time.Now()
	}
	n.data = resizeMemData(n.data, size)
	if auditTimer {
		s.ResizeNS += uint64(time.Since(start).Nanoseconds())
	}
	if auditEvents && strings.HasSuffix(a.Path, "/characterization.ibd") && s.Calls <= 128 {
		key := fmt.Sprintf("_growth_event|%s|%s|%03d|%d|%d|%d|%d", auditState.phase, op, s.Calls, oldLen, oldCap, size, cap(n.data))
		a.Phases[key] = &AuditStats{Calls: 1}
	}
	if size > int64(oldCap) {
		if oldCap == 0 {
			s.InitialCount++
			s.InitialCapacity += uint64(cap(n.data))
		} else {
			s.ReallocCount++
			s.ReallocCapacity += uint64(cap(n.data))
		}
		s.OldCopied += uint64(oldLen)
		if a.Mapped {
			s.DetachCount++
			s.Detached += uint64(oldLen)
			a.Mapped = false
		}
	} else if size > int64(oldLen) {
		s.Cleared += uint64(int(size) - oldLen)
	}
	if int(size) < oldLen {
		auditShrink(a, int(size))
	}
	auditNode(fs, n)
}
func (fs *MemFS) auditIO(n *memNode, off, count int, write bool) {
	if !auditEnabled || n.dir {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	if write {
		s := auditStats(a, "write")
		s.Calls++
		s.Write += uint64(count)
		auditCoverage(a, off, count)
	} else {
		s := auditStats(a, "read")
		s.Calls++
		s.Read += uint64(count)
	}
}
func (fs *MemFS) auditRequest(n *memNode, end int64) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	s := auditStats(a, "allocate-request")
	s.Calls++
	if end >= 0 && uint64(end) > s.RequestedEOF {
		s.RequestedEOF = uint64(end)
	}
}
func (fs *MemFS) auditTrunc(n *memNode) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	auditShrink(a, 0)
	a.Len = 0
}
func (fs *MemFS) auditPopulate(n *memNode) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	s := auditStats(a, "host-populate")
	s.InitialCount++
	s.InitialCapacity += uint64(cap(n.data))
	s.InputCopied += uint64(len(n.data))
	auditCoverage(a, 0, len(n.data))
}
func (fs *MemFS) auditMap(n *memNode) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	a := auditNode(fs, n)
	a.Mapped = true
	a.Imported = len(n.data)
}
func (fs *MemFS) AuditEnd() {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	for _, a := range auditState.nodes {
		if a.FS == fs.auditID {
			a.Ended = true
		}
	}
}

func AuditCheckpoint(phase string) {
	if !auditEnabled {
		return
	}
	auditState.Lock()
	defer auditState.Unlock()
	frame := AuditFrame{Phase: phase, ObserverAccounted: auditState.accounted, ObserverBitmap: auditState.bitmap}
	for _, a := range auditState.nodes {
		var touched, full int
		for _, v := range a.touched {
			touched += bits.OnesCount64(v)
		}
		for _, v := range a.full {
			full += bits.OnesCount64(v)
		}
		lower, upper := full*auditPage, touched*auditPage
		if upper > a.Len {
			upper = a.Len
		}
		if lower > a.Len {
			lower = a.Len
		}
		frame.Nodes = append(frame.Nodes, AuditPoint{a.ID, a.FS, a.Path, a.Role, a.Epoch, a.Len, a.Cap, a.Mapped, a.Imported, a.Linked, a.Handles, a.Ended, a.Overflow, lower, upper})
	}
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	frame.HeapAlloc = m.HeapAlloc
	frame.HeapInuse = m.HeapInuse
	frame.TotalAlloc = m.TotalAlloc
	frame.GC = m.NumGC
	if helper := os.Getenv("MARIAMEM_MEMFS_PROCESS_HELPER"); helper != "" {
		b, err := exec.Command(helper, strconv.Itoa(os.Getpid())).Output()
		if err != nil {
			frame.ProcessError = err.Error()
		} else {
			frame.Process = b
		}
	}
	auditState.frames = append(auditState.frames, frame)
}
func AuditSave(path string) error {
	if !auditEnabled {
		return nil
	}
	auditState.Lock()
	defer auditState.Unlock()
	b, err := json.MarshalIndent(map[string]any{"nodes": auditState.nodes, "frames": auditState.frames, "coverage_granule_bytes": auditPage, "coverage_max_file_bytes": auditMaxBytes, "resize_timer": auditTimer, "observer_accounted_bytes": auditState.accounted, "observer_bitmap_bytes": auditState.bitmap, "observer_scope": "metadata only; no FS/node/data references in global collector; accounting excludes maps, checkpoint slices, strings and serialization; upper/lower write coverage, explicit zero writes included; imported bytes separate"}, "", " ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0600)
}
