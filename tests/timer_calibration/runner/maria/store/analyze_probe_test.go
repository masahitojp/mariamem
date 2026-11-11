package store_test

import (
	"context"
	"encoding/json"
	"os"
	"time"

	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

// Preserve raw server responses even if their reported times are invalid.
// The Python assessment owns the expected correctness question; SQL liveness
// and resource cleanup remain assertions here.
func analyzeProbe() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	root, err := startBackend(ctx)
	must(err)
	p := root.open()
	_, err = p.ExecContext(ctx, "CREATE TABLE timer_probe(id INT PRIMARY KEY)")
	must(err)
	_, err = p.ExecContext(ctx, "INSERT INTO timer_probe VALUES (1),(2)")
	must(err)
	must(p.Close())
	must(root.wait())
	fork, closeSnapshot, err := root.snapshot()
	must(err)
	must(root.close())
	child, err := fork("analyze")
	must(err)
	p = child.open()
	p.SetMaxOpenConns(1)
	var rows []map[string]any
	for repeat := 0; repeat < 3; repeat++ {
		for _, delay := range []bool{false, true} {
			query := "ANALYZE FORMAT=JSON SELECT SUM(id) FROM timer_probe"
			if delay {
				query = "ANALYZE FORMAT=JSON SELECT SUM(id + SLEEP(0.01)) FROM timer_probe"
			}
			var raw string
			start := time.Now()
			err := p.QueryRowContext(ctx, query).Scan(&raw)
			row := map[string]any{"repeat": repeat, "delay": delay, "query": query,
				"wall_ms": float64(time.Since(start).Nanoseconds()) / 1e6, "raw": raw}
			if err != nil {
				row["error"] = err.Error()
			}
			rows = append(rows, row)
			var sum int
			must(p.QueryRowContext(ctx, "SELECT SUM(id) FROM timer_probe").Scan(&sum))
			if sum != 3 {
				panic("subsequent SELECT changed")
			}
		}
	}
	retire(child, p)
	must(closeSnapshot())
	mappings := base.MemoryMappingStats()["active_mappings"]
	if mappings != 0 {
		panic("mapping leak")
	}
	data, err := json.MarshalIndent(map[string]any{"rows": rows, "subsequent_select": "PASS",
		"active_mappings_after": mappings}, "", "  ")
	must(err)
	must(os.WriteFile(os.Getenv("ANALYZE_PROBE_PATH"), data, 0644))
	must(writeForkObservations(os.Getenv("FORK_STAGE_PATH")))
}
