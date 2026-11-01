package runner

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/workerphases/common"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"path/filepath"
	"runtime/pprof"
	"syscall"
	"time"
)

var PhaseHook func(string)
var Diagnostic func() any

type Phase struct {
	Name   string  `json:"name"`
	WallMS float64 `json:"wall_ms"`
	CPUMS  float64 `json:"cpu_ms"`
}
type Result struct {
	Success         bool              `json:"success"`
	Cleanup         bool              `json:"cleanup"`
	Error           string            `json:"error,omitempty"`
	Count           int               `json:"count"`
	QueriesPerChild int               `json:"queries_per_child"`
	Phases          []Phase           `json:"phases"`
	Final           map[string]uint64 `json:"final"`
	Diagnostic      any               `json:"diagnostic,omitempty"`
}

func cpu() float64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func run(target, dir string, count int, bad bool) (result Result, err error) {
	result.QueriesPerChild = 32
	ctx, cancel := common.Context()
	defer cancel()
	var profile bytes.Buffer
	phase := func(name string, fn func() error) error {
		if PhaseHook != nil {
			PhaseHook(name)
		}
		if name == target {
			profile.Reset()
			if e := pprof.StartCPUProfile(&profile); e != nil {
				return e
			}
		}
		c, w := cpu(), time.Now()
		e := fn()
		wall, used := float64(time.Since(w).Nanoseconds())/1e6, cpu()-c
		result.Phases = append(result.Phases, Phase{name, wall, used})
		if PhaseHook != nil {
			PhaseHook("outside")
		}
		if name == target {
			pprof.StopCPUProfile()
			e = errors.Join(e, os.WriteFile(filepath.Join(dir, fmt.Sprintf("%03d.pprof", result.Count)), profile.Bytes(), 0600))
		}
		return e
	}
	sn, e := common.Prepare(ctx)
	if e != nil {
		return result, e
	}
	var child *mariamem.Database
	defer func() {
		if child != nil {
			err = errors.Join(err, child.Close())
		}
		err = errors.Join(err, sn.Close())
		result.Final = base.MemoryMappingStats()
		result.Cleanup = result.Final["active_mappings"] == 0 && result.Final["active_rw_bytes"] == 0 && result.Final["active_reserved_bytes"] == 0
		result.Success = err == nil && result.Cleanup
		if err != nil {
			result.Error = err.Error()
		}
		if Diagnostic != nil {
			result.Diagnostic = Diagnostic()
		}
	}()
	for i := 0; i < count; i++ {
		if e = phase("fork", func() error { var e error; child, e = sn.Fork(ctx); return e }); e != nil {
			return result, e
		}
		if e = phase("sql", func() error {
			p, e := common.Connect(ctx, child)
			if e != nil {
				return e
			}
			defer p.Close()
			if bad {
				if _, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1"); e != nil {
					return e
				}
			}
			for j := 0; j < result.QueriesPerChild; j++ {
				if e = common.Oracle(ctx, p); e != nil {
					return e
				}
			}
			if _, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=v+1 WHERE id=1"); e != nil {
				return e
			}
			var n int
			if e = p.QueryRowContext(ctx, "SELECT SUM(v) FROM fork_probe").Scan(&n); e != nil {
				return e
			}
			if n != 500501 {
				return fmt.Errorf("mutation oracle: %d", n)
			}
			return common.Disconnect(ctx, child, p)
		}); e != nil {
			return result, e
		}
		if e = phase("close", child.Close); e != nil {
			return result, e
		}
		child = nil
		result.Count++
	}
	return result, nil
}
func Main() {
	out := flag.String("out", "", "report")
	target := flag.String("target", "none", "fork/sql/close/none")
	dir := flag.String("profiles", "", "profile directory")
	count := flag.Int("count", 40, "cycles <=40")
	bad := flag.Bool("corrupt", false, "negative SQL oracle")
	flag.Parse()
	if *out == "" || *count < 1 || *count > 40 {
		panic("invalid args")
	}
	if *target != "none" && *target != "fork" && *target != "sql" && *target != "close" {
		panic("invalid phase")
	}
	if *target != "none" {
		if e := os.MkdirAll(*dir, 0700); e != nil {
			panic(e)
		}
	}
	r, e := run(*target, *dir, *count, *bad)
	data, _ := json.MarshalIndent(r, "", "  ")
	if x := os.WriteFile(*out, append(data, '\n'), 0600); x != nil {
		panic(x)
	}
	if e != nil || !r.Success {
		os.Exit(1)
	}
}
