package observe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

type Event struct {
	Operation string `json:"operation"`
	Name      string `json:"name"`
	Offset    int64  `json:"offset_ns"`
}
type Record struct {
	Events []Event                    `json:"events,omitempty"`
	Traces map[string]json.RawMessage `json:"traces,omitempty"`
}

var mu sync.Mutex
var records = map[int]*Record{}

func Child(ctx context.Context, index int) context.Context {
	if os.Getenv("FORKCOST_TRACE") == "" {
		return ctx
	}
	start := time.Now()
	mu.Lock()
	records[index] = &Record{Traces: map[string]json.RawMessage{}}
	mu.Unlock()
	ctx = context.WithValue(ctx, "forkcost_child", index)
	return context.WithValue(ctx, "forkcost_event", func(op, name string, at time.Time) {
		mu.Lock()
		defer mu.Unlock()
		records[index].Events = append(records[index].Events, Event{op, name, at.Sub(start).Nanoseconds()})
	})
}
func Trace(ctx context.Context, operation string, v any) {
	if os.Getenv("FORKCOST_TRACE") == "" {
		return
	}
	index, ok := ctx.Value("forkcost_child").(int)
	if !ok {
		panic("missing trace child")
	}
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	mu.Lock()
	defer mu.Unlock()
	if _, exists := records[index].Traces[operation]; exists {
		panic("duplicate child operation: " + operation)
	}
	records[index].Traces[operation] = b
}
func complete() bool {
	for _, r := range records {
		ops := map[string]map[string]bool{}
		for _, e := range r.Events {
			if ops[e.Operation] == nil {
				ops[e.Operation] = map[string]bool{}
			}
			ops[e.Operation][e.Name] = true
		}
		if ops["pg_fork"] == nil {
			continue
		}
		if !ops["pg_close"]["end"] || !ops["pg_cluster_release"]["end"] {
			return false
		}
		for op, names := range ops {
			if len(op) >= 11 && op[:11] == "pg_process/" && !names["module_closed"] {
				return false
			}
		}
	}
	return true
}
func Flush() error {
	path := os.Getenv("FORKCOST_TRACE")
	if path == "" {
		return nil
	}
	start := time.Now()
	deadline := start.Add(10 * time.Second)
	for {
		mu.Lock()
		done := complete()
		mu.Unlock()
		if done {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("asynchronous cleanup trace incomplete")
		}
		time.Sleep(time.Millisecond)
	}
	mu.Lock()
	defer mu.Unlock()
	b, err := json.MarshalIndent(struct {
		Children         map[int]*Record `json:"children"`
		PostBatchDrainMS float64         `json:"post_batch_drain_ms"`
	}{records, float64(time.Since(start)) / 1e6}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0600)
}
