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
	"sync"
	"syscall"
	"time"
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
}

func Start(ctx context.Context, runtime, module, wasmerDir, transfer, restore string, stderr io.Writer) (*Process, error) {
	args := []string{"run", module, "--no-tty", "--volume", transfer + ":/snapshot-out"}
	if restore != "" {
		args = append(args, "--volume", restore+":/snapshot-in", "--", "--restore-snapshot")
	}
	cmd := exec.Command(runtime, args...)
	cmd.Env = os.Environ()
	if wasmerDir != "" {
		cmd.Env = append(cmd.Env, "WASMER_DIR="+wasmerDir)
	}
	cmd.Stderr = stderr
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
	if err = cmd.Start(); err != nil {
		in.Close()
		out.Close()
		return nil, err
	}
	readDone := make(chan struct{})
	go func() { defer close(readDone); p.read() }()
	go func() { <-readDone; p.exitErr = cmd.Wait(); close(p.done); p.fail(errors.New("guest exited")) }()
	select {
	case r := <-ready:
		if r.err == nil && r.result.Ready && r.result.Version == 2 && r.result.MaxSessions == 16 {
			p.SnapshotVersion = r.result.SnapshotVersion
			return p, nil
		}
		if r.err == nil {
			r.err = errors.New("unsupported guest: requires multi-session API v2")
		}
		return nil, p.AbortAndWait(r.err)
	case <-ctx.Done():
		return nil, p.AbortAndWait(ctx.Err())
	}
}
func (p *Process) PID() int              { return p.cmd.Process.Pid }
func (p *Process) Done() <-chan struct{} { return p.done }
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
		return err
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
		p.Abort(err)
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
	if export {
		saved = make(chan response, 1)
		p.pending[0] = saved
	}
	p.mu.Unlock()
	select {
	case <-p.done:
		if export {
			return errors.New("guest exited before snapshot")
		}
		return p.exitErr
	default:
	}
	frame := []byte{0, 0, 0, 0}
	if export {
		binary.LittleEndian.PutUint32(frame, 0xfffffffe)
	}
	if err := p.write(ctx, frame); err != nil {
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
