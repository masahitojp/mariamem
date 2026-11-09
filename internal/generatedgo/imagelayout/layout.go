// Package imagelayout describes a generated initial-memory image.
package imagelayout

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"reflect"
)

// Grain is independent of the generating host's OS page size.
const Grain = 4096

type Layout struct {
	Version      int               `json:"version"`
	MemoryBytes  uint64            `json:"memory_bytes"`
	Begin        uint64            `json:"begin"`
	End          uint64            `json:"end"`
	MemorySHA256 string            `json:"memory_sha256"`
	Globals      []uint64          `json:"globals"`
	DataEnd      uint32            `json:"data_end"`
	Dropped      []bool            `json:"dropped"`
	SourceSHA256 map[string]string `json:"source_sha256"`
}

// Discover deliberately scans the COMPLETE initial image during generation/check,
// never during ordinary Start/Fork. All zero pages are represented by anonymous
// zero memory; the envelope covers every nonzero byte, including init flags.
func Discover(memory []byte, globals []uint64, dataEnd uint32, dropped []bool, sources map[string]string) Layout {
	l := Layout{Version: 1, MemoryBytes: uint64(len(memory)), Globals: append([]uint64(nil), globals...), DataEnd: dataEnd, Dropped: append([]bool(nil), dropped...), SourceSHA256: sources}
	h := sha256.Sum256(memory)
	l.MemorySHA256 = hex.EncodeToString(h[:])
	zero := make([]byte, Grain)
	for off := 0; off < len(memory); off += Grain {
		end := min(off+Grain, len(memory))
		if !bytes.Equal(memory[off:end], zero[:end-off]) {
			if l.End == 0 {
				l.Begin = uint64(off)
			}
			l.End = uint64(end)
		}
	}
	return l
}

func (l Layout) Validate() error {
	if l.Version != 1 || l.MemoryBytes == 0 || l.MemoryBytes > 2<<30 || l.MemoryBytes%Grain != 0 || l.Begin%Grain != 0 || l.End%Grain != 0 || l.Begin > l.End || l.End > l.MemoryBytes || (l.Begin == l.End && l.End != 0) || uint64(l.DataEnd) > l.MemoryBytes {
		return fmt.Errorf("invalid initial-image bounds/version")
	}
	validHash := func(s string) bool { b, e := hex.DecodeString(s); return e == nil && len(b) == 32 }
	if !validHash(l.MemorySHA256) || len(l.SourceSHA256) == 0 {
		return fmt.Errorf("missing initial-image identity")
	}
	for _, v := range l.SourceSHA256 {
		if !validHash(v) {
			return fmt.Errorf("invalid source identity")
		}
	}
	return nil
}

func Decode(data []byte) (Layout, error) {
	var l Layout
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&l); err != nil {
		return l, err
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return l, fmt.Errorf("trailing layout data: %v", err)
	}
	if err := l.Validate(); err != nil {
		return l, err
	}
	// Canonical serialization is checked by the generator; no permissive fallback.
	return l, nil
}

func (l Layout) Bounds(page uint64) (uint64, uint64, error) {
	if err := l.Validate(); err != nil {
		return 0, 0, err
	}
	if page == 0 || page&(page-1) != 0 || page > l.MemoryBytes || l.MemoryBytes%page != 0 {
		return 0, 0, fmt.Errorf("unsupported page size")
	}
	return l.Begin / page * page, (l.End + page - 1) / page * page, nil
}

func (l Layout) MatchesState(memoryBytes uint64, globals []uint64, dataEnd uint32, dropped []bool) bool {
	return l.MemoryBytes == memoryBytes && reflect.DeepEqual(l.Globals, globals) && l.DataEnd == dataEnd && reflect.DeepEqual(l.Dropped, dropped)
}
