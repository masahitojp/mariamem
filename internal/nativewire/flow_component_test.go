package nativewire

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// The subprocess is the actual C++ controller with callback stimulus instead
// of MariaDB. No SQL, rollback correctness, WASIX or Snapshot artifact is proved.
func startFlowComponent(t *testing.T, timeout time.Duration) *Backend {
	t.Helper()
	program := os.Getenv("MARIAMEM_FLOW_COMPONENT")
	if program == "" {
		t.Skip("explicit controller component binary required")
	}
	var stderr bytes.Buffer
	runner := func(x Execution) <-chan error {
		done := make(chan error, 1)
		cmd := exec.Command(program)
		cmd.Env = append(os.Environ(), fmt.Sprintf("MARIAMEM_CONTROL_EPOCH=%d", x.Epoch))
		cmd.Stdin = x.Input
		cmd.Stdout = x.Output
		cmd.Stderr = &stderr
		if e := cmd.Start(); e != nil {
			done <- e
			return done
		}
		go func() { done <- cmd.Wait() }()
		return done
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	b, e := Start(ctx, Config{Runner: runner, Build: "controller-component-no-engine", QueryTimeout: timeout})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = b.Close(ctx)
		select {
		case <-b.Done():
		case <-ctx.Done():
			t.Fatal("controller/relay did not join")
		}
		t.Log(stderr.String())
	})
	return b
}

func flowConn(t *testing.T, b *Backend) net.Conn {
	t.Helper()
	c, e := b.DialContext(context.Background())
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { c.Close() })
	c.SetDeadline(time.Now().Add(10 * time.Second))
	return c
}

type flowStats struct {
	Joined, Started, Stale uint64
	Sessions               []struct {
		Phase       string
		Command     uint64
		Outstanding uint64
		QueuePeak   uint64 `json:"queue_peak"`
	}
}

func statsFlow(t *testing.T, b *Backend) flowStats {
	t.Helper()
	f, e := b.rpc(frame{kind: 7})
	if e != nil {
		t.Fatal(e)
	}
	var s flowStats
	if e = json.Unmarshal(f.body, &s); e != nil {
		t.Fatal(e)
	}
	return s
}
func waitFlow(t *testing.T, b *Backend, condition func(flowStats) bool) flowStats {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		s := statsFlow(t, b)
		if condition(s) {
			return s
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatal("controller observation not reached")
	return flowStats{}
}
func readFlow(t *testing.T, c net.Conn, n int) {
	t.Helper()
	v := make([]byte, n)
	if _, e := io.ReadFull(c, v); e != nil {
		t.Fatal(e)
	}
	for i, b := range v {
		if b != byte(i%251) {
			t.Fatalf("wrong byte at %d", i)
		}
	}
}
func TestFlowComponentBlockedOutputControlAndCapture(t *testing.T) {
	b := startFlowComponent(t, time.Minute)
	c := flowConn(t, b)
	if _, e := c.Write([]byte{'B', 'P'}); e != nil {
		t.Fatal(e)
	}
	s := waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Outstanding == outputLimit })
	if s.Sessions[0].QueuePeak > 4096 {
		t.Fatalf("guest queue peak %d", s.Sessions[0].QueuePeak)
	}
	if s.Sessions[0].Command != 1 {
		t.Fatal("next command admitted before blocked output was acknowledged")
	}
	f, e := b.rpc(frame{kind: kindCaptureFence, value: 1})
	if e != nil || f.kind != kindRejected || f.value != 1 {
		t.Fatal("capture did not reject busy output", f, e)
	}
	readFlow(t, c, 262144)
	readFlow(t, c, 1)
	waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Phase == "idle" })
	f, e = b.rpc(frame{kind: kindCaptureFence, value: 2})
	if e != nil || f.kind != kindFenced {
		t.Fatal("idle fence", f, e)
	}
}

func TestFlowComponentGrantIdentityAndRegression(t *testing.T) {
	b := startFlowComponent(t, time.Minute)
	c := flowConn(t, b)
	if _, err := c.Write([]byte{'B'}); err != nil {
		t.Fatal(err)
	}
	waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Outstanding == outputLimit })
	b.mu.Lock()
	var id key
	for k := range b.sessions {
		id = k
	}
	b.mu.Unlock()
	// Invalid credit for a different generation must never reach this session.
	if err := b.send(frame{kind: kindOutputGrant, slot: id.slot, generation: id.generation + 1, value: 0}); err != nil {
		t.Fatal(err)
	}
	s := statsFlow(t, b)
	if s.Stale != 1 || s.Sessions[0].Outstanding != outputLimit {
		t.Fatal("stale grant changed live session", s)
	}
	if err := b.send(frame{kind: kindOutputGrant, slot: id.slot, generation: id.generation, value: outputLimit - 1}); err != nil {
		t.Fatal(err)
	}
	select {
	case <-b.failed:
	case <-time.After(3 * time.Second):
		t.Fatal("regressing grant accepted")
	}
	if b.Failure() == nil || !strings.Contains(b.Failure().Error(), "output_grant_offset") {
		t.Fatal(b.Failure())
	}
}
func TestFlowComponentFragmentedWrites(t *testing.T) {
	b := startFlowComponent(t, time.Minute)
	c := flowConn(t, b)
	if _, e := c.Write([]byte{'F'}); e != nil {
		t.Fatal(e)
	}
	readFlow(t, c, 70000)
	waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Phase == "idle" })
}
func TestFlowComponentStopBlockedOutput(t *testing.T) {
	b := startFlowComponent(t, time.Minute)
	c := flowConn(t, b)
	c.Write([]byte{'B'})
	waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Outstanding == outputLimit })
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if e := b.Close(ctx); e != nil {
		t.Fatal(e)
	}
	select {
	case <-b.Done():
	default:
		t.Fatal("early close before join")
	}
}
func TestFlowComponentDisconnectAndIsolation(t *testing.T) {
	b := startFlowComponent(t, time.Minute)
	healthy := startFlowComponent(t, time.Minute)
	c := flowConn(t, b)
	c.Write([]byte{'B'})
	waitFlow(t, b, func(s flowStats) bool { return len(s.Sessions) == 1 && s.Sessions[0].Outstanding == outputLimit })
	c.Close()
	select {
	case <-b.failed:
	case <-time.After(3 * time.Second):
		t.Fatal("disconnect not observed at full window")
	}
	other := flowConn(t, healthy)
	other.Write([]byte{'P'})
	readFlow(t, other, 1)
}
func TestFlowComponentDeadlineStillLocal(t *testing.T) {
	b := startFlowComponent(t, 100*time.Millisecond)
	c := flowConn(t, b)
	c.Write([]byte{'B'})
	select {
	case <-b.failed:
	case <-time.After(3 * time.Second):
		t.Fatal("blocked output deadline missing")
	}
	if b.Failure() == nil {
		t.Fatal("missing cause")
	}
}
