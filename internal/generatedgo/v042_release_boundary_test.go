//go:build v042_release_probe

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
		h := &host{WasiStubs: base.DefaultWASI(), fdFlags: map[int32]uint16{}}
		m := generated.NewWithWASI(h, nil, h)
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
