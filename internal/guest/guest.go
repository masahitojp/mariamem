// Package guest owns the experimental WASIX subprocess and its framed API.
// This transport is internal: public database identity is independent of PIDs.
package guest

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/masahitojp/mariamem/internal/diagnostic"
	"github.com/masahitojp/mariamem/internal/timing"
)

type Column struct {
	Name     string `json:"name"`
	OrgName  string `json:"org_name"`
	Table    string `json:"table"`
	OrgTable string `json:"org_table"`
	DB       string `json:"db"`
	Catalog  string `json:"catalog"`
	Type     uint8  `json:"type"`
	Charset  uint16 `json:"charset"`
	Flags    uint16 `json:"flags"`
	Length   uint32 `json:"length"`
	Decimals uint8  `json:"decimals"`
}
type Cell struct {
	Hex string `json:"$h"`
}
type Result struct {
	OK              bool      `json:"ok"`
	Ready           bool      `json:"ready"`
	Closed          bool      `json:"closed"`
	Version         int       `json:"api_version"`
	MaxSessions     int       `json:"max_sessions"`
	SnapshotVersion int       `json:"snapshot_version"`
	Snapshot        bool      `json:"snapshot"`
	Status          uint16    `json:"server_status"`
	Warnings        uint16    `json:"warnings"`
	Errno           uint16    `json:"errno"`
	Error           string    `json:"error"`
	SQLState        string    `json:"sqlstate"`
	Affected        string    `json:"affected"`
	InsertID        string    `json:"insert_id"`
	Columns         []Column  `json:"columns"`
	Rows            [][]*Cell `json:"rows"`
}
type response struct {
	result Result
	err    error
}
type Process struct {
	cmd             *exec.Cmd
	in              io.WriteCloser
	out             io.ReadCloser
	mu              sync.Mutex
	next            uint32
	pending         map[uint32]chan response
	failure         error
	stopping        bool
	writes          chan struct{}
	done            chan struct{}
	exitErr         error
	abort           sync.Once
	SnapshotVersion int
	MaxSessions     int
}

func Start(ctx context.Context, runtime, module, wasmerDir, transfer, restore string, stderr io.Writer) (*Process, error) {
	args := []string{"run", module, "--no-tty", "--volume", transfer + ":/snapshot-out"}
	if timing.Enabled(ctx) {
		args = append(args, "--env", "MARIAMEM_GUEST_TIMING=1")
		if os.Getenv("MARIAMEM_INIT_DIAGNOSTICS") == "1" {
			args = append(args, "--env", "MARIAMEM_INIT_DIAGNOSTICS=1")
		}
	}
	if restore != "" {
		args = append(args, "--volume", restore+":/snapshot-in", "--", "--restore-snapshot")
	}
	cmd := exec.Command(runtime, args...)
	cmd.Env = os.Environ()
	if wasmerDir != "" {
		cmd.Env = append(cmd.Env, "WASMER_DIR="+wasmerDir)
	}
	tail := &stderrTail{}
	if stderr == nil {
		cmd.Stderr = tail
	} else {
		cmd.Stderr = io.MultiWriter(stderr, tail)
	}
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	in, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := cmd.StdoutPipe()
	if err != nil {
		in.Close()
		return nil, err
	}
	ready := make(chan response, 1)
	p := &Process{cmd: cmd, in: in, out: out, writes: make(chan struct{}, 1), done: make(chan struct{}), pending: map[uint32]chan response{0: ready}}
	timing.Mark(ctx, "spawn_begin")
	if err = cmd.Start(); err != nil {
		in.Close()
		out.Close()
		return nil, diagnostic.Wrap("guest_start", "guest_launch", fmt.Errorf("could not launch Wasmer %q for guest %q; use the complete native bundle for your supported platform and check executable permissions: %w", runtime, module, err))
	}
	timing.Mark(ctx, "spawn_returned")
	timing.Runtime(ctx, p.PID())
	readDone := make(chan struct{})
	go func() { defer close(readDone); p.read() }()
	go func() { <-readDone; p.exitErr = cmd.Wait(); close(p.done); p.fail(errors.New("guest exited")) }()
	select {
	case r := <-ready:
		if r.err == nil && r.result.Ready && r.result.Version == 2 && r.result.MaxSessions > 0 && r.result.MaxSessions <= 65536 {
			p.SnapshotVersion = r.result.SnapshotVersion
			p.MaxSessions = r.result.MaxSessions
			return p, nil
		}
		if r.err == nil {
			r.err = errors.New("unsupported guest: requires multi-session API v2 with valid capacity")
		}
		return nil, startupError(p.AbortAndWait(r.err), tail)
	case <-ctx.Done():
		return nil, startupError(p.AbortAndWait(ctx.Err()), tail)
	}
}
func (p *Process) PID() int              { return p.cmd.Process.Pid }
func (p *Process) Done() <-chan struct{} { return p.done }

// Err reports the cause that made the guest unusable, if any.
func (p *Process) Err() error {
	p.mu.Lock()
	err := p.failure
	p.mu.Unlock()
	if err != nil {
		select {
		case <-p.done:
			if p.exitErr != nil {
				return errors.Join(err, fmt.Errorf("guest process: %w", p.exitErr))
			}
		default:
		}
		return err
	}
	select {
	case <-p.done:
		if p.exitErr != nil {
			return fmt.Errorf("guest exited: %w", p.exitErr)
		}
		return errors.New("guest exited")
	default:
		return nil
	}
}
func (p *Process) fail(err error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.failure == nil {
		p.failure = err
	}
	for id, ch := range p.pending {
		ch <- response{err: err}
		delete(p.pending, id)
	}
}
func (p *Process) Abort(err error) {
	p.abort.Do(func() { p.fail(err); _ = syscall.Kill(-p.PID(), syscall.SIGKILL); p.in.Close(); p.out.Close() })
}

func (p *Process) AbortAndWait(err error) error {
	p.Abort(err)
	select {
	case <-p.done:
		return errors.Join(err, p.Err())
	case <-time.After(10 * time.Second):
		return fmt.Errorf("%w; guest cleanup timed out", err)
	}
}

func (p *Process) readFailed(err error) {
	p.mu.Lock()
	stopping := p.stopping
	p.mu.Unlock()
	if stopping {
		p.fail(err)
	} else {
		p.Abort(fmt.Errorf("guest output closed unexpectedly: %w", err))
	}
}
func (p *Process) read() {
	for {
		var h [4]byte
		if _, err := io.ReadFull(p.out, h[:]); err != nil {
			p.readFailed(err)
			return
		}
		n := binary.LittleEndian.Uint32(h[:])
		if n == 0 || n > 32<<20 {
			p.Abort(errors.New("invalid guest frame"))
			return
		}
		b := make([]byte, n)
		if _, err := io.ReadFull(p.out, b); err != nil {
			p.readFailed(err)
			return
		}
		var msg struct {
			ID     uint32 `json:"request_id"`
			Result Result `json:"result"`
		}
		if err := json.Unmarshal(b, &msg); err != nil {
			p.Abort(err)
			return
		}
		p.mu.Lock()
		ch := p.pending[msg.ID]
		delete(p.pending, msg.ID)
		p.mu.Unlock()
		if ch == nil {
			p.Abort(errors.New("unknown guest response ID"))
			return
		}
		ch <- response{result: msg.Result}
	}
}
func writeAll(w io.Writer, b []byte) error {
	for len(b) > 0 {
		n, err := w.Write(b)
		if err != nil {
			return err
		}
		if n == 0 {
			return io.ErrShortWrite
		}
		b = b[n:]
	}
	return nil
}
func (p *Process) write(ctx context.Context, b []byte) error {
	select {
	case p.writes <- struct{}{}:
	case <-ctx.Done():
		p.Abort(ctx.Err())
		return ctx.Err()
	}
	defer func() { <-p.writes }()
	complete := make(chan error, 1)
	go func() { complete <- writeAll(p.in, b) }()
	select {
	case err := <-complete:
		if err != nil {
			p.Abort(err)
		}
		return err
	case <-ctx.Done():
		p.Abort(ctx.Err())
		return ctx.Err()
	}
}
func (p *Process) Call(ctx context.Context, op byte, slot uint32, sql []byte) (Result, error) {
	if len(sql) > 1<<20 {
		return Result{}, errors.New("SQL exceeds 1 MiB")
	}
	ch := make(chan response, 1)
	p.mu.Lock()
	if p.failure != nil || p.stopping {
		err := p.failure
		if err == nil {
			err = errors.New("guest is stopping")
		}
		p.mu.Unlock()
		return Result{}, err
	}
	p.next++
	id := p.next
	p.pending[id] = ch
	p.mu.Unlock()
	packet := make([]byte, 13+len(sql))
	binary.LittleEndian.PutUint32(packet, uint32(9+len(sql)))
	packet[4] = op
	binary.LittleEndian.PutUint32(packet[5:], id)
	binary.LittleEndian.PutUint32(packet[9:], slot)
	copy(packet[13:], sql)
	if err := p.write(ctx, packet); err != nil {
		return Result{}, err
	}
	select {
	case r := <-ch:
		return r.result, r.err
	case <-ctx.Done():
		p.Abort(ctx.Err())
		return Result{}, ctx.Err()
	}
}
func (p *Process) Shutdown(ctx context.Context) error {
	return p.stop(ctx, false)
}
func (p *Process) Export(ctx context.Context) error {
	return p.stop(ctx, true)
}
func (p *Process) stop(ctx context.Context, export bool) error {
	var saved chan response
	p.mu.Lock()
	p.stopping = true
	failed := p.failure != nil
	if export {
		saved = make(chan response, 1)
		p.pending[0] = saved
	}
	p.mu.Unlock()
	if failed && !export {
		select {
		case <-p.done:
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	select {
	case <-p.done:
		if export {
			return errors.New("guest exited before snapshot")
		}
		return nil // Already reaped; the owner reports an unexpected exit separately.
	default:
	}
	frame := []byte{0, 0, 0, 0}
	if export {
		binary.LittleEndian.PutUint32(frame, 0xfffffffe)
	}
	if err := p.write(ctx, frame); err != nil {
		if !export && p.Err() != nil {
			select {
			case <-p.done:
				return nil
			case <-ctx.Done():
				return ctx.Err()
			}
		}
		return err
	}
	p.in.Close()
	if export {
		select {
		case r := <-saved:
			if r.err != nil {
				return p.AbortAndWait(r.err)
			}
			if !r.result.Snapshot || r.result.SnapshotVersion != 1 {
				return p.AbortAndWait(errors.New("invalid snapshot acknowledgement"))
			}
		case <-ctx.Done():
			return p.AbortAndWait(ctx.Err())
		}
	}
	select {
	case <-p.done:
		if p.exitErr != nil {
			return fmt.Errorf("guest shutdown: %w", p.exitErr)
		}
		return nil
	case <-ctx.Done():
		p.Abort(ctx.Err())
		return ctx.Err()
	}
}

// stderrTail bounds startup diagnostics without retaining the full runtime log.
type stderrTail struct {
	mu   sync.Mutex
	data []byte
}

func (t *stderrTail) Write(b []byte) (int, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	n := len(b)
	t.data = append(t.data, b...)
	if len(t.data) > 1024 {
		t.data = append([]byte(nil), t.data[len(t.data)-1024:]...)
	}
	return n, nil
}
func startupError(err error, tail *stderrTail) error {
	tail.mu.Lock()
	text := strings.TrimSpace(string(tail.data))
	tail.mu.Unlock()
	if text != "" {
		err = fmt.Errorf("%w; stderr tail: %s", err, text)
	}
	hint := "Check that the runtime and guest come from the same native bundle; re-extract the matching release bundle before retrying."
	if strings.Contains(strings.ToLower(text), "cpu features") || strings.Contains(strings.ToLower(text), "incompatible binary") {
		hint = "The AOT guest is incompatible with this runtime or CPU. Use the matching platform bundle; Ubuntu 24.04 x86_64 requires SSE2 and SSSE3 CPU features (including in a VM)."
	}
	return diagnostic.Wrap("guest_connection", "guest_ready", fmt.Errorf("Wasmer/guest startup did not complete the expected API v2 handshake. %s Cause: %w", hint, err))
}
