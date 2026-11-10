package preparedproto

import "testing"

func TestValidateBinaryRowAgainstEncoder(t *testing.T) {
	for _, typ := range []byte{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255} {
		lengths := []int{0, 1, 2, 4, 7, 8, 11, 12, 250, 251, 65535, 65536}
		for _, n := range lengths {
			for _, null := range []bool{false, true} {
				v := Value{ParameterType: ParameterType{Type: typ}, Null: null}
				if !null {
					v.Bytes = make([]byte, n)
				}
				row, err := EncodeBinaryRow([]Value{v}, 0xfffffe)
				if err != nil {
					continue
				}
				if err := ValidateBinaryRow(row, []ParameterType{v.ParameterType}, 0xfffffe); err != nil {
					t.Fatalf("type=%d n=%d null=%v: %v", typ, n, null, err)
				}
				for _, bad := range [][]byte{row[:len(row)-1], append(append([]byte{}, row...), 0)} {
					if ValidateBinaryRow(bad, []ParameterType{v.ParameterType}, 0xfffffe) == nil {
						t.Fatalf("accepted bad boundary type=%d n=%d null=%v", typ, n, null)
					}
				}
			}
		}
	}
}

func TestValidateBinaryRowRejectsMalformedStructure(t *testing.T) {
	for _, tc := range []struct {
		name  string
		row   []byte
		types []ParameterType
	}{
		{"header", []byte{1, 0, 1}, []ParameterType{{Type: 1}}},
		{"reserved bitmap", []byte{0, 1, 1}, []ParameterType{{Type: 1}}},
		{"unused bitmap", []byte{0, 128, 1}, []ParameterType{{Type: 1}}},
		{"unknown null", []byte{0, 4}, []ParameterType{{Type: 200}}},
		{"null type nonnull", []byte{0, 0}, []ParameterType{{Type: 6}}},
		{"nonminimal length", []byte{0, 0, 252, 1, 0, 65}, []ParameterType{{Type: 253}}},
		{"null length", []byte{0, 0, 251}, []ParameterType{{Type: 253}}},
		{"temporal width", []byte{0, 0, 1, 0}, []ParameterType{{Type: 11}}},
		{"huge length", []byte{0, 0, 254, 255, 255, 255, 255, 255, 255, 255, 255}, []ParameterType{{Type: 253}}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if ValidateBinaryRow(tc.row, tc.types, 0xfffffe) == nil {
				t.Fatal("accepted malformed row")
			}
		})
	}
	for n := 1; n <= 18; n++ {
		values := make([]Value, n)
		types := make([]ParameterType, n)
		for i := range values {
			types[i] = ParameterType{Type: 1}
			values[i] = Value{ParameterType: types[i], Null: i%2 == 0}
			if !values[i].Null {
				values[i].Bytes = []byte{42}
			}
		}
		row, err := EncodeBinaryRow(values, 100)
		if err != nil {
			t.Fatal(err)
		}
		if ValidateBinaryRow(row, types, len(row)) != nil {
			t.Fatalf("bitmap n=%d", n)
		}
		if ValidateBinaryRow(row, types, len(row)-1) == nil {
			t.Fatal("budget bypass")
		}
	}
}
