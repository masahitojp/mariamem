//go:build integration

package generatedgo

import (
	"encoding/binary"
	"encoding/json"
	"io"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

type trappingDup struct{ base.Wasix_32v1Imports }

func (trappingDup) Fd_dup(*base.Module, int32, int32) int32 { panic("injected fd_dup worker trap") }

type trapGuest struct {
	in       *os.File
	out      *os.File
	done     <-chan error
	failed   chan error
	sequence uint32
}

func startTrapGuest(t *testing.T, inject bool) *trapGuest {
	t.Helper()
	childIn, in, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	out, childOut, err := os.Pipe()
	if err != nil {
		childIn.Close()
		in.Close()
		t.Fatal(err)
	}
	g := &trapGuest{in: in, out: out, failed: make(chan error, 1)}
	g.done = startInstance(childIn, childOut, io.Discard, "", nil, false, func(err error) {
		g.failed <- err
		// Exactly as Process.Abort: fail callers and close transport, then join.
		in.Close()
		out.Close()
	}, func(h *host) (*base.Module, func() error, error) {
		m, release, err := newMemoryModule(h)
		if err == nil && inject {
			m.Wasix_32v1 = trappingDup{m.Wasix_32v1}
		}
		return m, release, err
	})
	t.Cleanup(func() { in.Close(); out.Close(); childIn.Close(); childOut.Close() })
	read := make(chan error, 1)
	go func() { _, err := g.read(); read <- err }()
	select {
	case err := <-read:
		if err != nil {
			t.Fatal("guest ready", err)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("guest ready timed out")
	}
	return g
}

func (g *trapGuest) read() (map[string]any, error) {
	var header [4]byte
	if _, err := io.ReadFull(g.out, header[:]); err != nil {
		return nil, err
	}
	body := make([]byte, binary.LittleEndian.Uint32(header[:]))
	if _, err := io.ReadFull(g.out, body); err != nil {
		return nil, err
	}
	var frame struct {
		Result map[string]any `json:"result"`
	}
	if err := json.Unmarshal(body, &frame); err != nil {
		return nil, err
	}
	return frame.Result, nil
}

func (g *trapGuest) call(op byte, sql string) (map[string]any, error) {
	g.sequence++
	frame := make([]byte, 13+len(sql))
	binary.LittleEndian.PutUint32(frame, uint32(9+len(sql)))
	frame[4] = op
	binary.LittleEndian.PutUint32(frame[5:], g.sequence)
	copy(frame[13:], sql)
	if _, err := g.in.Write(frame); err != nil {
		return nil, err
	}
	return g.read()
}

func TestWorkerTrapActualGuestNotifiesAndIsolatesPeer(t *testing.T) {
	before := base.MemoryMappingStats()
	broken, healthy := startTrapGuest(t, true), startTrapGuest(t, false)
	for _, g := range []*trapGuest{broken, healthy} {
		for _, command := range []struct {
			op  byte
			sql string
		}{{1, ""}, {2, "CREATE TABLE t(v TEXT)"}, {2, "INSERT INTO t VALUES('alice'),('alice'),('bob')"}} {
			r, err := g.call(command.op, command.sql)
			if err != nil || r["ok"] != true {
				t.Fatal("setup", r, err)
			}
		}
	}
	query := make(chan error, 1)
	go func() { _, err := broken.call(2, "SELECT DISTINCT v FROM t"); query <- err }()
	select {
	case err := <-broken.failed:
		if !strings.Contains(err.Error(), "injected fd_dup worker trap") {
			t.Fatal(err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("actual SQL worker trap was not reported promptly")
	}
	select {
	case err := <-query:
		if err == nil {
			t.Fatal("failed query returned success")
		}
	case <-time.After(3 * time.Second):
		t.Fatal("failed query still awaiting response")
	}
	select {
	case err := <-broken.done:
		if err == nil || !strings.Contains(err.Error(), "injected fd_dup worker trap") {
			t.Fatal("lost joined trap", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("cooperative trapped DB did not join")
	}
	if r, err := healthy.call(2, "SELECT DISTINCT v FROM t"); err != nil || r["ok"] != true {
		t.Fatal("peer DB poisoned", r, err)
	}
	if _, err := healthy.in.Write([]byte{0, 0, 0, 0}); err != nil {
		t.Fatal(err)
	}
	select {
	case err := <-healthy.done:
		if err != nil {
			t.Fatal("healthy shutdown", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("healthy DB did not shut down")
	}
	after := base.MemoryMappingStats()
	if after["active_mappings"] != before["active_mappings"] || after["releases"] != before["releases"]+2 {
		t.Fatal("instance mappings retained", before, after)
	}
}
