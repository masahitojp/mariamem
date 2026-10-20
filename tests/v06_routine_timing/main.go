// Diagnostic only: retrieve the existing guest timing file after orderly Close.
// Same StartInstance/prepared handles and exact guest; no generated-source edits.
package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/prepared"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"os"
	"path/filepath"
	"runtime"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func one(ctx context.Context, entries []prepared.Entry) json.RawMessage {
	dir, err := os.MkdirTemp("", "routine-timing-")
	must(err)
	defer os.RemoveAll(dir)
	childIn, in, err := os.Pipe()
	must(err)
	defer childIn.Close()
	defer in.Close()
	out, childOut, err := os.Pipe()
	must(err)
	defer out.Close()
	defer childOut.Close()
	var logs bytes.Buffer
	capture := &prepared.Capture{}
	completed := generatedgo.StartInstance(childIn, childOut, &logs, dir, entries, true, capture)
	process, err := guest.Connect(ctx, in, out, completed, func() { childIn.Close(); childOut.Close() }, &logs)
	if err != nil {
		panic(fmt.Sprint(err, "; ", logs.String()))
	}
	must(process.Shutdown(ctx))
	data, err := os.ReadFile(filepath.Join(dir, "startup-timing.json"))
	must(err)
	if !json.Valid(data) {
		panic("invalid guest timing")
	}
	return data
}
func main() {
	output := flag.String("output", "", "evidence JSON")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	var logs bytes.Buffer
	s, err := host.StartGenerated(ctx, nil, 30*time.Second, &logs)
	must(err)
	defer s.Close(ctx)
	q, err := sql.Open("mysql", fmt.Sprintf("root@tcp(127.0.0.1:%d)/test", s.Port()))
	must(err)
	_, err = q.Exec("CREATE FUNCTION test.timing_value() RETURNS INT DETERMINISTIC RETURN 9")
	must(err)
	must(q.Close())
	deadline := time.Now().Add(5 * time.Second)
	for s.Active() != 0 {
		if time.Now().After(deadline) {
			panic("connection cleanup timeout")
		}
		time.Sleep(time.Millisecond)
	}
	owned, consumed, err := s.SnapshotHeap(ctx, false)
	must(err)
	if !consumed {
		panic("not consumed")
	}
	defer owned.Close()
	entries, release, err := owned.Acquire(runtimekind.GuestSHA256)
	must(err)
	defer release()
	var pairs []map[string]any
	for i := 0; i < 6; i++ {
		pairs = append(pairs, map[string]any{"pair": i, "fresh": one(ctx, nil), "restore": one(ctx, entries)})
	}
	data, err := json.MarshalIndent(map[string]any{"classification": "diagnostic, six paired modes in one warm Go host; each guest starts anew; not a before/after benchmark", "guest_sha256": generatedgo.GuestSHA256, "go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "pairs": pairs}, "", "  ")
	must(err)
	if *output != "" {
		must(os.WriteFile(*output, append(data, '\n'), 0644))
	}
	fmt.Println(string(data))
}
