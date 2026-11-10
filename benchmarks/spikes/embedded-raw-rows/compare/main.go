package main

import (
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/masahitojp/mariamem/internal/preparedproto"
	"os"
)

type Column struct {
	Type  byte   `json:"type"`
	Flags uint16 `json:"flags"`
}
type Cell struct {
	Hex string `json:"$h"`
}
type Record struct {
	Case    string    `json:"case"`
	RawOnly bool      `json:"raw_only"`
	Part    int       `json:"part"`
	Columns []Column  `json:"columns"`
	Rows    [][]*Cell `json:"rows"`
	Raw     []string  `json:"raw"`
}

func main() {
	f, err := os.Open(os.Args[1])
	if err != nil {
		panic(err)
	}
	defer f.Close()
	scan := bufio.NewScanner(f)
	scan.Buffer(make([]byte, 4096), 32<<20)
	paired := map[string]Record{}
	only := map[string]Record{}
	failures := []string{}
	rows := 0
	payloadBytes := 0
	negative := false
	for scan.Scan() {
		var r Record
		if err := json.Unmarshal(scan.Bytes(), &r); err != nil {
			panic(err)
		}
		key := fmt.Sprintf("%s/%d", r.Case, r.Part)
		if r.RawOnly {
			only[key] = r
			continue
		}
		paired[key] = r
		if len(r.Rows) != len(r.Raw) {
			failures = append(failures, key+": row count")
			continue
		}
		for n, row := range r.Rows {
			if len(row) != len(r.Columns) {
				panic("column count")
			}
			values := make([]preparedproto.Value, len(row))
			for i, c := range row {
				values[i] = preparedproto.Value{ParameterType: preparedproto.ParameterType{Type: r.Columns[i].Type, Unsigned: r.Columns[i].Flags&32 != 0}, Null: c == nil}
				if c != nil {
					values[i].Bytes, err = hex.DecodeString(c.Hex)
					if err != nil {
						panic(err)
					}
				}
			}
			expected, e := preparedproto.EncodeBinaryRow(values, 0xfffffe)
			if e != nil {
				failures = append(failures, key+": "+e.Error())
				continue
			}
			actual, e := hex.DecodeString(r.Raw[n])
			if e != nil {
				panic(e)
			}
			rows++
			payloadBytes += len(actual)
			if !bytes.Equal(expected, actual) {
				failures = append(failures, fmt.Sprintf("%s row%d: expected %d bytes raw %d bytes; first differing byte %d", key, n, len(expected), len(actual), firstDiff(expected, actual)))
			}
			if len(actual) > 1 && bytes.Equal(expected, actual) {
				mutated := append([]byte(nil), actual...)
				mutated[len(mutated)-1] ^= 1
				negative = negative || !bytes.Equal(expected, mutated)
			}
		}
	}
	if e := scan.Err(); e != nil {
		panic(e)
	}
	for key, r := range paired {
		other, ok := only[key]
		if !ok {
			failures = append(failures, key+": missing raw-only")
			continue
		}
		a, _ := json.Marshal(r.Raw)
		b, _ := json.Marshal(other.Raw)
		ac, _ := json.Marshal(r.Columns)
		bc, _ := json.Marshal(other.Columns)
		if !bytes.Equal(a, b) || !bytes.Equal(ac, bc) {
			failures = append(failures, key+": raw-only differs")
		}
	}
	if len(paired) == 0 || len(paired) != len(only) || rows == 0 || !negative {
		failures = append(failures, "missing observations or negative control")
	}
	result := map[string]any{"paired_results": len(paired), "raw_only_results": len(only), "rows": rows, "payload_bytes": payloadBytes, "mutation_detected": negative, "failures": failures, "pass": len(failures) == 0}
	out, _ := json.MarshalIndent(result, "", "  ")
	fmt.Println(string(out))
	if len(failures) != 0 {
		os.Exit(1)
	}
}
func firstDiff(a, b []byte) int {
	n := min(len(a), len(b))
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return n
}
