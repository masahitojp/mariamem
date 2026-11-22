//go:build integration

package generatedgo

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/prepared"
)

type trappingDup struct{ base.Wasix_32v1Imports }

func (trappingDup) Fd_dup(*base.Module, int32, int32) int32 { panic("injected fd_dup worker trap") }

type wireEnvelope struct {
	kind       byte
	request    uint32
	slot       uint32
	epoch      uint64
	generation uint64
	value      uint64
	body       []byte
}

type trapGuest struct {
	in       *os.File
	out      *os.File
	done     <-chan error
	failed   chan error
	reqSeq   uint32
	sentOff  uint64
	ackedOff uint64
	rxBuf    bytes.Buffer
}

func (g *trapGuest) writeEnv(f wireEnvelope) error {
	raw := make([]byte, 37+len(f.body))
	binary.LittleEndian.PutUint32(raw[0:4], uint32(33+len(f.body)))
	raw[4] = f.kind
	binary.LittleEndian.PutUint32(raw[5:9], f.request)
	binary.LittleEndian.PutUint32(raw[9:13], f.slot)
	binary.LittleEndian.PutUint64(raw[13:21], f.epoch)
	binary.LittleEndian.PutUint64(raw[21:29], f.generation)
	binary.LittleEndian.PutUint64(raw[29:37], f.value)
	copy(raw[37:], f.body)
	_, err := g.in.Write(raw)
	return err
}

func (g *trapGuest) readEnv() (wireEnvelope, error) {
	var hdr [4]byte
	if _, err := io.ReadFull(g.out, hdr[:]); err != nil {
		return wireEnvelope{}, err
	}
	n := binary.LittleEndian.Uint32(hdr[:])
	if n < 33 {
		return wireEnvelope{}, fmt.Errorf("short wire envelope: %d", n)
	}
	raw := make([]byte, n)
	if _, err := io.ReadFull(g.out, raw); err != nil {
		return wireEnvelope{}, err
	}
	return wireEnvelope{
		kind:       raw[0],
		request:    binary.LittleEndian.Uint32(raw[1:5]),
		slot:       binary.LittleEndian.Uint32(raw[5:9]),
		epoch:      binary.LittleEndian.Uint64(raw[9:17]),
		generation: binary.LittleEndian.Uint64(raw[17:25]),
		value:      binary.LittleEndian.Uint64(raw[25:33]),
		body:       raw[33:],
	}, nil
}

func (g *trapGuest) readMySQLPacket() ([]byte, error) {
	for {
		if g.rxBuf.Len() >= 4 {
			b := g.rxBuf.Bytes()
			plen := int(b[0]) | int(b[1])<<8 | int(b[2])<<16
			if g.rxBuf.Len() >= 4+plen {
				out := make([]byte, plen)
				_ = g.rxBuf.Next(4)
				copy(out, g.rxBuf.Next(plen))
				return out, nil
			}
		}
		env, err := g.readEnv()
		if err != nil {
			return nil, err
		}
		if env.kind == 103 { // OUTPUT
			g.rxBuf.Write(env.body)
			g.ackedOff = env.value + uint64(len(env.body))
			_ = g.writeEnv(wireEnvelope{kind: 3, slot: 0, epoch: 1, generation: 1, value: g.ackedOff})
		} else if env.kind == 105 { // POISON
			return nil, fmt.Errorf("guest poison: %s", string(env.body))
		}
	}
}

func (g *trapGuest) writeMySQLPacket(seq byte, payload []byte) error {
	pkt := make([]byte, 4+len(payload))
	n := len(payload)
	pkt[0], pkt[1], pkt[2], pkt[3] = byte(n), byte(n>>8), byte(n>>16), seq
	copy(pkt[4:], payload)
	off := g.sentOff
	g.sentOff += uint64(len(pkt))
	return g.writeEnv(wireEnvelope{kind: 2, slot: 0, epoch: 1, generation: 1, value: off, body: pkt})
}

func (g *trapGuest) openSession() error {
	g.reqSeq++
	if err := g.writeEnv(wireEnvelope{kind: 1, request: g.reqSeq, slot: 0, epoch: 1, generation: 1, value: uint64(30 * time.Second)}); err != nil {
		return err
	}
	// Read initial greeting packet
	if _, err := g.readMySQLPacket(); err != nil {
		return err
	}
	var auth bytes.Buffer
	flags := uint32(1 | 512 | 32768 | 524288 | 8)
	_ = binary.Write(&auth, binary.LittleEndian, flags)
	_ = binary.Write(&auth, binary.LittleEndian, uint32(16*1024*1024))
	auth.WriteByte(45)
	auth.Write(make([]byte, 23))
	auth.WriteString("root\x00\x00test\x00mysql_native_password\x00")
	if err := g.writeMySQLPacket(1, auth.Bytes()); err != nil {
		return err
	}
	reply, err := g.readMySQLPacket()
	if err != nil {
		return err
	}
	if len(reply) == 0 || reply[0] != 0x00 {
		return fmt.Errorf("auth failed: %x", reply)
	}
	return nil
}

func (g *trapGuest) execSQL(sql string) error {
	if err := g.writeMySQLPacket(0, append([]byte{0x03}, sql...)); err != nil {
		return err
	}
	first, err := g.readMySQLPacket()
	if err != nil {
		return err
	}
	if len(first) == 0 {
		return fmt.Errorf("empty SQL reply")
	}
	if first[0] == 0x00 {
		return nil
	}
	if first[0] == 0xff {
		return fmt.Errorf("mysql error: %x", first)
	}
	// Result set: read columns until EOF, then rows until EOF.
	for phase := 0; phase < 2; phase++ {
		for {
			p, err := g.readMySQLPacket()
			if err != nil {
				return err
			}
			if len(p) > 0 && p[0] == 0xff {
				return fmt.Errorf("mysql result error: %x", p)
			}
			if len(p) > 0 && len(p) < 9 && p[0] == 0xfe {
				break
			}
		}
	}
	return nil
}

func (g *trapGuest) stop() error {
	return g.writeEnv(wireEnvelope{kind: 6, epoch: 1})
}

func runWireSQLQueries(in, out *os.File, queries []string) error {
	g := &trapGuest{in: in, out: out}
	env, err := g.readEnv()
	if err != nil {
		return err
	}
	if env.kind != 100 {
		return fmt.Errorf("expected READY(100), got %d", env.kind)
	}
	if err := g.openSession(); err != nil {
		return err
	}
	for _, sql := range queries {
		if err := g.execSQL(sql); err != nil {
			return err
		}
	}
	if err := g.writeMySQLPacket(0, []byte{0x01}); err != nil { // COM_QUIT
		return err
	}
	if err := g.writeEnv(wireEnvelope{kind: 4, slot: 0, epoch: 1, generation: 1, value: 0}); err != nil { // PEER_EOF
		return err
	}
	return g.stop()
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
	var capture prepared.Capture
	g.done = startWireInstance(childIn, childOut, io.Discard, "", nil, false, func(err error) {
		select {
		case g.failed <- err:
		default:
		}
		in.Close()
		out.Close()
	}, func(h *host) (*base.Module, func() error, error) {
		m, release, err := newMemoryModule(h)
		if err == nil && inject {
			m.Wasix_32v1 = trappingDup{m.Wasix_32v1}
		}
		return m, release, err
	}, 1, &WireLifecycle{Capture: &capture, Approval: make(chan error, 1)})
	t.Cleanup(func() { in.Close(); out.Close(); childIn.Close(); childOut.Close() })
	read := make(chan error, 1)
	go func() {
		env, err := g.readEnv()
		if err == nil && env.kind != 100 {
			err = fmt.Errorf("expected READY(100), got %d", env.kind)
		}
		read <- err
	}()
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

func TestWorkerTrapActualGuestNotifiesAndIsolatesPeer(t *testing.T) {
	warmProcessImage(t)
	before := base.MemoryMappingStats()
	broken, healthy := startTrapGuest(t, true), startTrapGuest(t, false)
	for _, g := range []*trapGuest{broken, healthy} {
		if err := g.openSession(); err != nil {
			t.Fatal("openSession", err)
		}
		for _, sql := range []string{"CREATE TABLE t(v TEXT)", "INSERT INTO t VALUES('alice'),('alice'),('bob')"} {
			if err := g.execSQL(sql); err != nil {
				t.Fatal("setup", sql, err)
			}
		}
	}
	query := make(chan error, 1)
	go func() { query <- broken.execSQL("SELECT DISTINCT v FROM t") }()
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
	if err := healthy.execSQL("SELECT DISTINCT v FROM t"); err != nil {
		t.Fatal("peer DB poisoned", err)
	}
	if err := healthy.stop(); err != nil {
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

func TestActualGuestStoppedBeforeMemoryRelease(t *testing.T) {
	warmProcessImage(t)
	before := base.MemoryMappingStats()["active_mappings"]
	childIn, in, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	out, childOut, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { in.Close(); out.Close(); childIn.Close(); childOut.Close() })
	gate := make(chan struct{})
	entered := make(chan struct{})
	stopped := make(chan error, 1)
	var once sync.Once
	t.Cleanup(func() { once.Do(func() { close(gate) }) })
	g := &trapGuest{in: in, out: out}
	var capture prepared.Capture
	g.done = startWireInstance(childIn, childOut, io.Discard, "", nil, false, nil,
		func(h *host) (*base.Module, func() error, error) {
			m, release, err := newMemoryModule(h)
			if err != nil {
				return nil, nil, err
			}
			return m, func() error { close(entered); <-gate; return release() }, nil
		}, 1, &WireLifecycle{
			Capture:   &capture,
			Approval:  make(chan error, 1),
			OnStopped: func(err error) { stopped <- err },
		})
	ready := make(chan error, 1)
	go func() {
		env, err := g.readEnv()
		if err == nil && env.kind != 100 {
			err = fmt.Errorf("expected READY(100), got %d", env.kind)
		}
		ready <- err
	}()
	select {
	case err := <-ready:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("ready timeout")
	}
	if err := g.openSession(); err != nil {
		t.Fatal(err)
	}
	if err := g.execSQL("SET GLOBAL innodb_fast_shutdown=2"); err != nil {
		t.Fatal(err)
	}
	if err := g.stop(); err != nil {
		t.Fatal(err)
	}
	in.Close()
	select {
	case err := <-stopped:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("missing actual guest stopped")
	}
	<-entered
	if got := base.MemoryMappingStats()["active_mappings"]; got != before+1 {
		t.Fatal("memory not retained at stopped", got, before)
	}
	select {
	case <-g.done:
		t.Fatal("cleanup completed while release gated")
	default:
	}
	childIn.Close()
	childOut.Close()
	out.Close()
	once.Do(func() { close(gate) })
	select {
	case err := <-g.done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("cleanup timeout")
	}
	if got := base.MemoryMappingStats()["active_mappings"]; got != before {
		t.Fatal("mapping leak", got, before)
	}
}
