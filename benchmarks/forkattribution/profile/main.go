package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/masahitojp/mariamem/benchmarks/forkattribution/common"
	"os"
	"runtime/pprof"
	"syscall"
	"time"
)

type Result struct {
	Success bool    `json:"success"`
	Count   int     `json:"count"`
	WallMS  float64 `json:"wall_ms"`
	CPUms   float64 `json:"cpu_ms"`
	Error   string  `json:"error,omitempty"`
}

func cpu() float64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return float64(r.Utime.Sec+r.Stime.Sec)*1000 + float64(r.Utime.Usec+r.Stime.Usec)/1000
}
func run(profile string, count int, corrupt bool) (r Result, err error) {
	ctx, cancel := common.Context()
	defer cancel()
	sn, e := common.Prepare(ctx)
	if e != nil {
		return r, e
	}
	defer func() { err = errors.Join(err, sn.Close()) }()
	f, e := os.Create(profile)
	if e != nil {
		return r, e
	}
	defer f.Close()
	if e = pprof.StartCPUProfile(f); e != nil {
		return r, e
	}
	defer pprof.StopCPUProfile()
	start, at := cpu(), time.Now()
	for i := 0; i < count; i++ {
		d, e := sn.Fork(ctx)
		if e != nil {
			return r, e
		}
		e = common.CheckChild(ctx, d, corrupt)
		e = errors.Join(e, d.Close())
		if e != nil {
			return r, e
		}
		r.Count++
	}
	r.WallMS = float64(time.Since(at)) / 1e6
	r.CPUms = cpu() - start
	return r, nil
}
func main() {
	out := flag.String("out", "", "report")
	profile := flag.String("profile", "", "profile")
	count := flag.Int("count", 100, "children")
	corrupt := flag.Bool("corrupt", false, "negative oracle")
	flag.Parse()
	if *out == "" || *profile == "" || *count < 1 || *count > 100 {
		panic("invalid arguments")
	}
	r, e := run(*profile, *count, *corrupt)
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
