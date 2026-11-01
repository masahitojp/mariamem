package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/growthprototype/common"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"syscall"
	"time"
)

type Child struct {
	WallMS       float64 `json:"wall_ms"`
	CPUMS        float64 `json:"cpu_ms"`
	GrowCalls    uint64  `json:"grow_calls"`
	ProtectCalls uint64  `json:"protect_calls"`
	Fallbacks    uint64  `json:"fallbacks"`
}
type Result struct {
	Success  bool              `json:"success"`
	Error    string            `json:"error,omitempty"`
	Cleanup  bool              `json:"cleanup"`
	Children []Child           `json:"children"`
	Final    map[string]uint64 `json:"final"`
}

var input = bufio.NewReader(os.Stdin)

func checkpoint(name string) {
	b, _ := json.Marshal(map[string]any{"checkpoint": name})
	fmt.Println(string(b))
	if _, e := input.ReadString('\n'); e != nil {
		panic(e)
	}
}
func cpu() float64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func run(corrupt bool) (result Result, err error) {
	ctx, cancel := common.Context()
	defer cancel()
	var children []*mariamem.Database
	sn, e := common.Prepare(ctx)
	if e != nil {
		return result, e
	}
	defer func() {
		for _, d := range children {
			err = errors.Join(err, d.Close())
		}
		err = errors.Join(err, sn.Close())
		result.Final = base.MemoryMappingStats()
		result.Cleanup = result.Final["active_mappings"] == 0
		result.Success = err == nil && result.Cleanup
		if err != nil {
			result.Error = err.Error()
		}
		checkpoint("closed")
	}()
	runtime.GC()
	checkpoint("baseline")
	for i := 0; i < 4; i++ {
		before := base.MemoryMappingStats()
		c := cpu()
		w := time.Now()
		d, e := sn.Fork(ctx)
		wall := float64(time.Since(w).Nanoseconds()) / 1e6
		used := cpu() - c
		if e != nil {
			return result, e
		}
		children = append(children, d)
		after := base.MemoryMappingStats()
		result.Children = append(result.Children, Child{wall, used, after["grow_calls"] - before["grow_calls"], after["protect_calls"] - before["protect_calls"], after["protect_fallbacks"] - before["protect_fallbacks"]})
		if e = common.CheckChild(ctx, d, corrupt && i == 0); e != nil {
			return result, e
		}
		p, e := common.Connect(ctx, d)
		if e != nil {
			return result, e
		}
		_, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=v+1 WHERE id=1")
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return result, e
		}
		checkpoint(fmt.Sprintf("child-%d", i+1))
	}
	for _, d := range children {
		p, e := common.Connect(ctx, d)
		if e != nil {
			return result, e
		}
		var n, total int
		e = p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &total)
		e = errors.Join(e, common.Disconnect(ctx, d, p))
		if e != nil {
			return result, e
		}
		if n != 1000 || total != 500501 {
			return result, fmt.Errorf("independent mutation oracle %d %d", n, total)
		}
	}
	return result, nil
}
func main() {
	out := flag.String("out", "", "result")
	bad := flag.Bool("corrupt", false, "negative oracle")
	flag.Parse()
	r, e := run(*bad)
	data, _ := json.MarshalIndent(r, "", "  ")
	if err := os.WriteFile(*out, append(data, '\n'), 0600); err != nil {
		panic(err)
	}
	if e != nil || !r.Success {
		os.Exit(1)
	}
}
