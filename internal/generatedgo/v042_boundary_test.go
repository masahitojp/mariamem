//go:build experiment_mmap && ((darwin && arm64) || (linux && amd64))

package generatedgo

import (
	"encoding/binary"
	"fmt"
	generated "github.com/masahitojp/mariamem/internal/generatedgo/code"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p8"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"testing"
)

// A legal import stub isolates the real generated load at static offset 8.
// WASM i32 addition for the import's output address wraps; load memarg does not.
type v042Clock struct{ *base.WasiStubs }

func (v042Clock) Clock_time_get(m *base.Module, clock int32, precision int64, out int32) int32 {
	binary.LittleEndian.PutUint64(m.Memory[uint32(out):], 1000000000)
	return 0
}

// This intentionally fails when the required WASM scalar trap contract fails.
// Illegal generated accesses run only in disposable child processes.
func TestV042RequiredScalarBounds(t *testing.T) {
	if probe := os.Getenv("V042_BOUNDARY_CHILD"); probe != "" {
		m, release, err := experimentMappedModule(experimentTestHost())
		if err != nil {
			panic(err)
		}
		defer release()
		defer func() {
			if p := recover(); p != nil {
				fmt.Printf("RECOVERED_TRAP: %v\n", p)
				os.Exit(0)
			}
		}()
		switch probe {
		case "initial-oob":
			m.G1 = generated.InitialMemoryBytes - 4
			fmt.Println(p8.Fn68(m))
		case "width-crosses-end":
			m.G1 = generated.InitialMemoryBytes - 6
			fmt.Println(p8.Fn68(m))
		case "offset-overflow":
			m.Wasi_snapshot_preview1 = v042Clock{base.DefaultWASI()}
			m.G0 = 8
			fmt.Println("Fn80 return", p8.Fn80(m, 0, 65536))
		}
		fmt.Println("ACCESS_RETURNED_WITHOUT_TRAP")
		os.Exit(10)
	}
	for _, probe := range []string{"initial-oob", "width-crosses-end", "offset-overflow"} {
		t.Run(probe, func(t *testing.T) {
			cmd := exec.Command(os.Args[0], "-test.run=^TestV042RequiredScalarBounds$")
			cmd.Env = append(os.Environ(), "V042_BOUNDARY_CHILD="+probe)
			cmd.SysProcAttr = nil
			output, err := cmd.CombinedOutput()
			// A fatal Go fault kills the parent product process, not just a WASM instance.
			if err != nil || !strings.Contains(string(output), "RECOVERED_TRAP:") {
				t.Errorf("required instance-level trap absent: exit=%v output=%.1400s", err, output)
			}
		})
	}
}

func TestV042MultipleGrowPreserveZeroAndFailure(t *testing.T) {
	m, release, err := experimentMappedModule(experimentTestHost())
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	ptr := m.M
	m.Memory[generated.InitialMemoryBytes-1] = 91
	for _, pages := range []int32{1, 2, 3} {
		old := m.MemSize.Load()
		if base.MemoryGrow(m, pages) != int32(old>>16) {
			t.Fatal("grow")
		}
		for offset := old; offset < m.MemSize.Load(); offset += 4096 {
			if m.Memory[offset] != 0 {
				t.Fatal("not zero", offset)
			}
			m.Memory[offset] = 17
		}
		if m.M != ptr || m.Memory[generated.InitialMemoryBytes-1] != 91 {
			t.Fatal("preservation/stability")
		}
	}
	size := m.MemSize.Load()
	tail := m.Memory[size-4096]
	commit := m.ExperimentMemoryCommit
	m.ExperimentMemoryCommit = func(uint64, uint64) error { return syscall.ENOMEM }
	if base.MemoryGrow(m, 1) != -1 || m.MemSize.Load() != size || m.M != ptr || m.Memory[size-4096] != tail {
		t.Fatal("failure changed state")
	}
	m.ExperimentMemoryCommit = commit
	for _, c := range []struct {
		addr, offset int32
		width        uint64
	}{{-1, 1, 4}, {int32(size - 2), 0, 4}, {-8, 8, 8}} {
		func() {
			defer func() {
				if recover() == nil {
					t.Error("atomic OOB missing", c)
				}
			}()
			base.AtomicEA(m, c.addr, c.offset, c.width)
		}()
	}
}
