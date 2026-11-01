package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem/benchmarks/forkattribution/common"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"sync"
)

type Step struct {
	Phase string `json:"phase"`
	Old   uint64 `json:"old"`
	Next  uint64 `json:"next"`
}
type Child struct {
	Index   int               `json:"index"`
	Steps   []Step            `json:"steps"`
	Success bool              `json:"success"`
	Cleanup bool              `json:"cleanup_complete"`
	Before  map[string]uint64 `json:"before"`
	After   map[string]uint64 `json:"after"`
}
type Result struct {
	Success  bool    `json:"success"`
	Cleanup  bool    `json:"cleanup_complete"`
	Children []Child `json:"children"`
	Error    string  `json:"error,omitempty"`
}

func run(corrupt bool) (r Result, err error) {
	ctx, cancel := common.Context()
	defer cancel()
	sn, e := common.Prepare(ctx)
	if e != nil {
		return r, e
	}
	defer func() {
		e := sn.Close()
		r.Cleanup = e == nil && base.MemoryMappingStats()["active_mappings"] == 0
		err = errors.Join(err, e)
	}()
	for i := 0; i < 2; i++ {
		c := Child{Index: i, Before: base.MemoryMappingStats()}
		var mu sync.Mutex
		phase := "fork"
		base.GrowthTraceHook = func(old, next uint64) { mu.Lock(); c.Steps = append(c.Steps, Step{phase, old, next}); mu.Unlock() }
		d, e := sn.Fork(ctx)
		if e != nil {
			base.GrowthTraceHook = nil
			return r, e
		}
		mu.Lock()
		phase = "verify"
		mu.Unlock()
		e = common.CheckChild(ctx, d, corrupt)
		if e == nil {
			p, ce := common.Connect(ctx, d)
			e = ce
			if e == nil {
				_, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1")
				if e == nil {
					var v int
					e = p.QueryRowContext(ctx, "SELECT v FROM fork_probe WHERE id=1").Scan(&v)
					if e == nil && v != -1 {
						e = fmt.Errorf("mutation value=%d", v)
					}
				}
				e = errors.Join(e, common.Disconnect(ctx, d, p))
			}
		}
		mu.Lock()
		phase = "close"
		mu.Unlock()
		ce := d.Close()
		base.GrowthTraceHook = nil
		c.After = base.MemoryMappingStats()
		c.Cleanup = ce == nil && c.After["active_mappings"] == 0
		e = errors.Join(e, ce)
		c.Success = e == nil
		r.Children = append(r.Children, c)
		if e != nil {
			return r, e
		}
		if uint64(len(c.Steps)) != c.After["grow_calls"]-c.Before["grow_calls"] {
			return r, errors.New("missed growth event")
		}
	}
	return r, nil
}
func main() {
	out := flag.String("out", "", "report")
	corrupt := flag.Bool("corrupt", false, "negative seed oracle")
	flag.Parse()
	if *out == "" {
		panic("-out required")
	}
	r, e := run(*corrupt)
	r.Success = e == nil
	if e != nil {
		r.Error = e.Error()
	}
	data, j := json.MarshalIndent(r, "", "  ")
	if j == nil {
		j = os.WriteFile(*out, append(data, '\n'), 0600)
	}
	if e != nil || j != nil {
		fmt.Fprintln(os.Stderr, errors.Join(e, j))
		os.Exit(1)
	}
}
