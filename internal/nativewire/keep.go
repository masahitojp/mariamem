package nativewire

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"time"

	stored "github.com/masahitojp/mariamem/internal/snapshot"
	"github.com/masahitojp/mariamem/internal/timing"
)

const errLockWaitTimeout = 1205

type guestStats struct {
	Sessions []struct {
		Slot       uint32 `json:"slot"`
		Generation uint64 `json:"generation"`
		Phase      string `json:"phase"`
		Status     uint64 `json:"status"`
	} `json:"sessions"`
}

func (r *Backend) queryStats(ctx context.Context) (guestStats, error) {
	reply, err := r.rpcContext(ctx, frame{kind: kindStats})
	if err != nil {
		return guestStats{}, err
	}
	if reply.kind != kindStatsReply {
		return guestStats{}, fmt.Errorf("unexpected STATS reply kind %d", reply.kind)
	}
	var st guestStats
	if err := json.Unmarshal(reply.body, &st); err != nil {
		return guestStats{}, fmt.Errorf("invalid STATS payload: %w", err)
	}
	return st, nil
}

func (r *Backend) setHold(ctx context.Context, k key, hold uint64) (bool, error) {
	reply, err := r.rpcContext(ctx, frame{kind: kindHold, slot: k.slot, generation: k.generation, value: hold})
	if err != nil {
		return false, err
	}
	// Stale (5) means the session has not opened yet or already retired.
	// Callers must NOT treat stale as confirmed HOLD=1 while the session is still reserved.
	if reply.kind == kindRejected && reply.value == 5 {
		return false, nil
	}
	if reply.kind != kindReply {
		return false, fmt.Errorf("unexpected HOLD reply kind %d", reply.kind)
	}
	return true, nil
}

// openPrivateSession opens an internal maintenance session over net.Pipe()
// while keepHold blocks external admissions. Returns the client conn, session key,
// and a wait function that confirms full slot release.
func (r *Backend) openPrivateSession(ctx context.Context, dbName string) (net.Conn, key, func(), error) {
	r.mu.Lock()
	if r.stopping || r.consumed || r.failure != nil {
		r.mu.Unlock()
		return nil, key{}, nil, ErrClosed
	}
	client, server := net.Pipe()
	s, err := r.reserveLocked(server)
	if err != nil {
		r.mu.Unlock()
		_ = client.Close()
		_ = server.Close()
		if errors.Is(err, ErrExhausted) {
			go r.fail(err)
		}
		return nil, key{}, nil, err
	}
	k := s.id
	r.wg.Add(1)
	r.mu.Unlock()

	go func() { defer r.wg.Done(); r.attach(s) }()

	waitRetired := func() {
		for {
			r.mu.Lock()
			_, stillPresent := r.sessions[k]
			if !stillPresent {
				r.mu.Unlock()
				return
			}
			if r.disconnectChanged == nil {
				r.disconnectChanged = make(chan struct{})
			}
			ch := r.disconnectChanged
			r.mu.Unlock()
			select {
			case <-ch:
			case <-r.done:
				return
			}
		}
	}

	if err := privateHandshake(ctx, client, dbName); err != nil {
		_ = client.Close()
		waitRetired()
		return nil, key{}, nil, err
	}
	return client, k, waitRetired, nil
}

// SnapshotKeep captures committed state without stopping the instance. Existing
// idle sessions stay attached; the source continues accepting SQL afterwards.
func (r *Backend) SnapshotKeep(ctx context.Context) (owned *stored.Owned, err error) {
	ctx, finish := timing.Begin(ctx, "snapshot_keep")
	defer finish()
	if e := ctx.Err(); e != nil {
		return nil, e
	}
	select {
	case r.operation <- struct{}{}:
		defer func() { <-r.operation }()
	case <-ctx.Done():
		return nil, ctx.Err()
	}

	checkBase := func() error {
		r.mu.Lock()
		defer r.mu.Unlock()
		if !r.SnapshotCapable() {
			return &Rejected{"unsupported", "guest does not support snapshots"}
		}
		if r.failure != nil {
			return errors.Join(&Rejected{"unusable", "database instance terminated"}, r.failure)
		}
		if r.stopping || r.consumed {
			return &Rejected{"closed", "database is closing"}
		}
		return nil
	}

	var releaseList []key
	releaseSet := make(map[key]bool)
	confirmedHeld := make(map[key]bool)
	releaseAll := func() {
		relCtx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
		defer cancel()
		var releaseErr error
		for _, k := range releaseList {
			if _, e := r.setHold(relCtx, k, 0); e != nil {
				rel := fmt.Errorf("release snapshot keep hold: %w", e)
				releaseErr = errors.Join(releaseErr, rel)
				r.mu.Lock()
				alive := !r.stopping && !r.consumed && r.failure == nil
				r.mu.Unlock()
				if alive {
					r.fail(rel)
				}
			}
		}
		releaseList = nil
		r.mu.Lock()
		if r.keepHold {
			r.keepHold = false
			if r.keepReleased != nil {
				close(r.keepReleased)
				r.keepReleased = nil
			}
		}
		r.mu.Unlock()
		if releaseErr != nil {
			err = errors.Join(err, &Rejected{"unusable", releaseErr.Error()}, releaseErr)
		}
		if err != nil && owned != nil {
			cleanupErr := owned.Close()
			owned = nil
			if cleanupErr != nil {
				r.mu.Lock()
				r.captureDebt = errors.Join(r.captureDebt, cleanupErr)
				r.mu.Unlock()
				err = errors.Join(err, cleanupErr)
			}
		}
	}
	defer releaseAll()

	// Wait until all existing sessions are held & idle with no open transactions.
	for {
		if e := checkBase(); e != nil {
			return nil, e
		}
		if e := ctx.Err(); e != nil {
			return nil, e
		}

		// Acquire keepHold so no new external connections enter while we quiesce & hold.
		r.mu.Lock()
		if r.failure != nil {
			f := r.failure
			r.mu.Unlock()
			return nil, errors.Join(&Rejected{"unusable", "database instance terminated"}, f)
		}
		if r.stopping || r.consumed {
			r.mu.Unlock()
			return nil, &Rejected{"closed", "database is closing"}
		}
		if !r.keepHold {
			r.keepHold = true
			r.keepReleased = make(chan struct{})
		}
		// Check if any session is currently busy (non-idle) or still opening.
		keys := make([]key, 0, len(r.sessions))
		anyOpening := false
		for k, s := range r.sessions {
			keys = append(keys, k)
			if s.phase != "idle" {
				anyOpening = true
			}
		}
		if r.activityChanged == nil {
			r.activityChanged = make(chan struct{})
		}
		actCh := r.activityChanged
		r.mu.Unlock()

		// Record each session in releaseList BEFORE sending HOLD=1 so that even if
		// ctx cancels after the guest applies HOLD=1 (before REPLY arrives),
		// defer releaseAll() always sends an idempotent HOLD=0 to unblock it.
		// Track confirmedHeld separately: a stale reply before OPEN reaches the
		// guest does NOT confirm HOLD=1, so we retry while the session remains reserved.
		allHeld := true
		for _, k := range keys {
			if confirmedHeld[k] {
				continue
			}
			if !releaseSet[k] {
				releaseSet[k] = true
				releaseList = append(releaseList, k)
			}
			applied, e := r.setHold(ctx, k, 1)
			if e != nil {
				return nil, e
			}
			if applied {
				confirmedHeld[k] = true
			} else {
				r.mu.Lock()
				_, stillReserved := r.sessions[k]
				r.mu.Unlock()
				if stillReserved {
					allHeld = false
				}
			}
		}

		// Authoritatively verify session phases & transaction status from guest STATS.
		st, e := r.queryStats(ctx)
		if e != nil {
			return nil, e
		}
		allIdle := !anyOpening && allHeld
		inTrans := false
		for _, s := range st.Sessions {
			sk := key{s.Slot, s.Generation}
			if !confirmedHeld[sk] {
				allIdle = false
			}
			if s.Phase != "idle" {
				allIdle = false
			} else if s.Status&1 != 0 {
				inTrans = true
			}
		}
		if inTrans {
			return nil, &Rejected{"transaction_active", "commit or roll back open transactions before a snapshot that keeps the database"}
		}
		if allIdle {
			break
		}

		// Some session is still busy; release hold briefly? No, keeping HOLD=1 prevents
		// finished sessions from starting another command while busy sessions finish!
		select {
		case <-actCh:
		case <-r.failed:
			return nil, checkBase()
		case <-r.done:
			return nil, &Rejected{"closed", "database is closing"}
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(5 * time.Millisecond):
		}
	}

	if e := ctx.Err(); e != nil {
		return nil, e
	}
	timing.Mark(ctx, "sessions_quiesced")

	// Open the private maintenance session in the default database ("test").
	// Once opened, operations up to UNLOCK + close are not ctx-cancelled so we
	// never leave a global read lock orphaned.
	guestCtx := context.WithoutCancel(ctx)
	conn, _, waitRetired, openErr := r.openPrivateSession(guestCtx, "test")
	if openErr != nil {
		if errors.Is(openErr, ErrCapacity) {
			return nil, &Rejected{"capacity", "snapshot requires one free session slot"}
		}
		return nil, fmt.Errorf("snapshot keep session open: %w", openErr)
	}

	var unlockErr error
	defer func() {
		qErr := privateWritePkt(conn, 0, []byte{0x01})
		cErr := conn.Close()
		waitRetired()
		closeErr := errors.Join(qErr, cErr)
		if unlockErr != nil && closeErr != nil {
			r.fail(errors.Join(unlockErr, closeErr))
		}
	}()

	if _, e := privateExec(guestCtx, conn, "SET SESSION lock_wait_timeout=0"); e != nil {
		return nil, fmt.Errorf("snapshot keep lock_wait_timeout: %w", e)
	}
	if rows, e := privateExec(guestCtx, conn, "XA RECOVER"); e != nil {
		return nil, fmt.Errorf("snapshot keep XA RECOVER: %w", e)
	} else if rows > 0 {
		return nil, &Rejected{"transaction_active", "a prepared XA transaction exists; run XA COMMIT or XA ROLLBACK first"}
	}
	if _, e := privateExec(guestCtx, conn, "FLUSH TABLES WITH READ LOCK"); e != nil {
		var mErr *privateMySQLError
		if errors.As(e, &mErr) && mErr.errno == errLockWaitTimeout {
			return nil, &Rejected{"busy", "a session holds LOCK TABLES ... WRITE; run UNLOCK TABLES first"}
		}
		return nil, fmt.Errorf("snapshot keep FTWRL: %w", e)
	}
	defer func() {
		if _, ue := privateExec(guestCtx, conn, "UNLOCK TABLES"); ue != nil {
			unlockErr = fmt.Errorf("snapshot keep UNLOCK TABLES: %w", ue)
			err = errors.Join(err, unlockErr)
		}
	}()

	timing.Mark(ctx, "tables_flushed")
	if _, e := privateExec(guestCtx, conn, "SET GLOBAL innodb_log_checkpoint_now=ON"); e != nil {
		return nil, fmt.Errorf("snapshot keep checkpoint: %w", e)
	}
	timing.Mark(ctx, "engine_checkpointed")
	root, e := r.capture.KeepRoot()
	if e != nil {
		return nil, e
	}
	timing.Mark(ctx, "files_cut")
	return stored.OwnRoot(root, r.build)
}

type privateMySQLError struct {
	errno uint16
	msg   string
}

func (e *privateMySQLError) Error() string {
	return fmt.Sprintf("errno %d: %s", e.errno, e.msg)
}

func privateReadPkt(c net.Conn) ([]byte, error) {
	_ = c.SetReadDeadline(time.Now().Add(30 * time.Second))
	var h [4]byte
	if _, err := io.ReadFull(c, h[:]); err != nil {
		return nil, err
	}
	n := int(h[0]) | int(h[1])<<8 | int(h[2])<<16
	b := make([]byte, n)
	if _, err := io.ReadFull(c, b); err != nil {
		return nil, err
	}
	return b, nil
}

func privateWritePkt(c net.Conn, seq byte, p []byte) error {
	_ = c.SetWriteDeadline(time.Now().Add(30 * time.Second))
	f := make([]byte, 4+len(p))
	f[0], f[1], f[2], f[3] = byte(len(p)), byte(len(p)>>8), byte(len(p)>>16), seq
	copy(f[4:], p)
	_, err := c.Write(f)
	return err
}

func privateParseErr(p []byte) error {
	if len(p) < 3 || p[0] != 0xff {
		return nil
	}
	errno := binary.LittleEndian.Uint16(p[1:3])
	msg := string(p[3:])
	if len(p) >= 9 && p[3] == '#' {
		msg = string(p[9:])
	}
	return &privateMySQLError{errno: errno, msg: msg}
}

func privateHandshake(_ context.Context, c net.Conn, dbName string) error {
	if _, err := privateReadPkt(c); err != nil {
		return err
	}
	flags := uint32(1 | 512 | 32768 | 524288)
	if dbName != "" {
		flags |= 8 // CLIENT_CONNECT_WITH_DB
	}
	var resp bytes.Buffer
	_ = binary.Write(&resp, binary.LittleEndian, flags)
	_ = binary.Write(&resp, binary.LittleEndian, uint32(16*1024*1024))
	resp.WriteByte(45)
	resp.Write(make([]byte, 23))
	resp.WriteString("root\x00\x00")
	if dbName != "" {
		resp.WriteString(dbName)
		resp.WriteByte(0)
	}
	resp.WriteString("mysql_native_password\x00")
	if err := privateWritePkt(c, 1, resp.Bytes()); err != nil {
		return err
	}
	reply, err := privateReadPkt(c)
	if err != nil {
		return err
	}
	if len(reply) == 0 {
		return errors.New("empty auth reply")
	}
	if reply[0] == 0xff {
		return privateParseErr(reply)
	}
	if reply[0] != 0x00 {
		return fmt.Errorf("unexpected auth packet 0x%02x", reply[0])
	}
	return nil
}

// privateExec executes a text COM_QUERY and returns the row count (0 for OK).
func privateExec(_ context.Context, c net.Conn, sql string) (int, error) {
	payload := make([]byte, 1+len(sql))
	payload[0] = 0x03
	copy(payload[1:], sql)
	if err := privateWritePkt(c, 0, payload); err != nil {
		return 0, err
	}
	first, err := privateReadPkt(c)
	if err != nil {
		return 0, err
	}
	if len(first) == 0 {
		return 0, errors.New("empty query reply")
	}
	if first[0] == 0x00 {
		return 0, nil
	}
	if first[0] == 0xff {
		return 0, privateParseErr(first)
	}
	// Result set: read column definitions until EOF, then rows until EOF.
	for {
		p, err := privateReadPkt(c)
		if err != nil {
			return 0, err
		}
		if len(p) > 0 && p[0] == 0xff {
			return 0, privateParseErr(p)
		}
		if len(p) < 9 && len(p) > 0 && p[0] == 0xfe {
			break
		}
	}
	rows := 0
	for {
		p, err := privateReadPkt(c)
		if err != nil {
			return 0, err
		}
		if len(p) > 0 && p[0] == 0xff {
			return 0, privateParseErr(p)
		}
		if len(p) < 9 && len(p) > 0 && p[0] == 0xfe {
			break
		}
		rows++
	}
	return rows, nil
}
