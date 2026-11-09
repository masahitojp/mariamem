// Generate/check an initial-image layout from actual generated constructor bytes.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/masahitojp/mariamem/benchmarks/staticlayout"
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func run() (err error) {
	root := flag.String("root", ".", "source root")
	output := flag.String("output", "benchmarks/staticimage/layout.json", "layout path")
	check := flag.Bool("check", false, "read-only equality check")
	flag.Parse()
	sources := map[string]string{}
	dir := filepath.Join(*root, "internal/generatedgo/code")
	err = filepath.WalkDir(dir, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(path, "_test.go") || (!strings.HasSuffix(path, ".go") && !strings.HasSuffix(path, ".s")) {
			return nil
		}
		data, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		h := sha256.Sum256(data)
		rel, e := filepath.Rel(*root, path)
		if e != nil {
			return e
		}
		sources[filepath.ToSlash(rel)] = hex.EncodeToString(h[:])
		return nil
	})
	if err != nil {
		return err
	}
	b, err := base.NewMemoryMapping(generated.InitialMemoryBytes, 2<<30)
	if err != nil {
		return err
	}
	defer func() {
		if e := b.Close(); e != nil {
			err = fmt.Errorf("layout mapping cleanup: %v (prior: %v)", e, err)
		}
	}()
	m := generated.NewWithMemory(nil, nil, nil, b.Bytes(), generated.InitialMemoryBytes)
	dropped := make([]bool, len(m.DataSegs))
	for i, v := range m.DataSegs {
		dropped[i] = v == nil
	}
	layout := staticlayout.Discover(m.Memory[:generated.InitialMemoryBytes], base.SaveGlobals(m), m.DataEnd, dropped, sources)
	if err = layout.Validate(); err != nil {
		return err
	}
	data, err := json.MarshalIndent(layout, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if *check {
		old, e := os.ReadFile(*output)
		if e != nil {
			return e
		}
		if !bytes.Equal(old, data) {
			return fmt.Errorf("layout differs: source inventory, complete initial bytes or metadata changed; regenerate and review")
		}
	} else if err = os.WriteFile(*output, data, 0644); err != nil {
		return err
	}
	fmt.Printf("layout %s: initial=%d envelope=[%d,%d) sha256=%s sources=%d\n", map[bool]string{true: "CHECK PASS", false: "GENERATED"}[*check], layout.MemoryBytes, layout.Begin, layout.End, layout.MemorySHA256, len(sources))
	return nil
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
