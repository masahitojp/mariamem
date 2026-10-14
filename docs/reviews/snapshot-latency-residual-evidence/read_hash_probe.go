package main

// Read-only proxy over the exact persisted Snapshot data. It does not measure
// the public Snapshot operation or change its validation/ownership contract.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
	"syscall"
	"time"
)

type sample struct {
	Block       int     `json:"block"`
	Mode        string  `json:"mode"`
	WallSeconds float64 `json:"wall_seconds"`
	CPUseconds  float64 `json:"cpu_seconds"`
	Bytes       int64   `json:"bytes"`
}

func cpu() float64 {
	var r syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &r); err != nil {
		panic(err)
	}
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}

func pass(files []string, hashing bool) (int64, map[string]string) {
	type result struct {
		path, hash string
		bytes      int64
		err        error
	}
	jobs := make(chan string)
	results := make(chan result, len(files))
	var workers sync.WaitGroup
	for w := 0; w < 2; w++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			buf := make([]byte, 32*1024)
			for path := range jobs {
				file, err := os.Open(path)
				if err != nil {
					results <- result{path: path, err: err}
					continue
				}
				h := sha256.New()
				var count int64
				for {
					n, e := file.Read(buf)
					count += int64(n)
					if hashing && n > 0 {
						_, err = h.Write(buf[:n])
						if err != nil {
							break
						}
					}
					if e == io.EOF {
						break
					}
					if e != nil {
						err = e
						break
					}
				}
				if e := file.Close(); err == nil {
					err = e
				}
				item := result{path: path, bytes: count, err: err}
				if hashing {
					item.hash = hex.EncodeToString(h.Sum(nil))
				}
				results <- item
			}
		}()
	}
	for _, file := range files {
		jobs <- file
	}
	close(jobs)
	workers.Wait()
	close(results)
	var total int64
	hashes := map[string]string{}
	for item := range results {
		if item.err != nil {
			panic(item.err)
		}
		total += item.bytes
		if hashing {
			hashes[item.path] = item.hash
		}
	}
	return total, hashes
}

func main() {
	if len(os.Args) != 3 {
		panic("usage: read_hash_probe SNAPSHOT_ROOT OUTPUT_JSON")
	}
	root := filepath.Join(os.Args[1], "data")
	var files []string
	var expected int64
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		if !entry.Type().IsRegular() {
			return fmt.Errorf("not regular: %s", path)
		}
		info, e := entry.Info()
		if e != nil {
			return e
		}
		files = append(files, path)
		expected += info.Size()
		return nil
	})
	if err != nil {
		panic(err)
	}
	sort.Strings(files)
	if len(files) == 0 || expected < 200*1024*1024 {
		panic("unexpected data fixture")
	}
	baselineHashes := map[string]string{}
	var samples []sample
	for block := -1; block < 7; block++ {
		order := []bool{false, true}
		if block%2 != 0 {
			order = []bool{true, false}
		}
		for _, hashing := range order {
			name := "read_only"
			if hashing {
				name = "read_and_sha256"
			}
			c0, t0 := cpu(), time.Now()
			got, hashes := pass(files, hashing)
			entry := sample{Block: block, Mode: name, WallSeconds: time.Since(t0).Seconds(), CPUseconds: cpu() - c0, Bytes: got}
			if got != expected {
				panic("read byte count changed")
			}
			if hashing {
				if len(baselineHashes) == 0 {
					baselineHashes = hashes
				} else {
					for file, want := range baselineHashes {
						if hashes[file] != want {
							panic("hash changed")
						}
					}
				}
			}
			samples = append(samples, entry)
			fmt.Println(block, name, entry.WallSeconds, entry.CPUseconds)
		}
	}
	output := map[string]any{"go": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH,
		"gomaxprocs": runtime.GOMAXPROCS(0), "file_count": len(files), "bytes_per_pass": expected,
		"workers": 2, "buffer_bytes": 32 * 1024, "warmup_block": -1, "samples": samples,
		"checksum_file_count": len(baselineHashes)}
	data, err := json.MarshalIndent(output, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.WriteFile(os.Args[2], append(data, '\n'), 0600); err != nil {
		panic(err)
	}
}
