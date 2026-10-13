package mysqlwire

import (
	"encoding/hex"
	"github.com/masahitojp/mariamem/internal/guest"
	"testing"
)

func identityCell(value string) *guest.Cell {
	return &guest.Cell{Hex: hex.EncodeToString([]byte(value))}
}

func TestConnectionIdentityVersion(t *testing.T) {
	for _, version := range []string{"12.3.3-MariaDB-embedded", "12.3.3", "13.1.0-MariaDB-embedded"} {
		r := guest.Result{OK: true, Rows: [][]*guest.Cell{{identityCell("42"), identityCell(version)}}}
		id, got, err := connectionIdentity(r)
		if err != nil || id != 42 || string(got) != version {
			t.Fatalf("identity altered: id=%d version=%q error=%v", id, got, err)
		}
	}
}

func TestConnectionIdentityRejectsInvalidResponse(t *testing.T) {
	tests := map[string]guest.Result{
		"query failure":   {OK: false},
		"missing row":     {OK: true},
		"missing version": {OK: true, Rows: [][]*guest.Cell{{identityCell("42")}}},
		"null version":    {OK: true, Rows: [][]*guest.Cell{{identityCell("42"), nil}}},
		"null id":         {OK: true, Rows: [][]*guest.Cell{{nil, identityCell("12.3.3")}}},
		"empty version":   {OK: true, Rows: [][]*guest.Cell{{identityCell("42"), identityCell("")}}},
		"nul version":     {OK: true, Rows: [][]*guest.Cell{{identityCell("42"), identityCell("12.3.3\x00")}}},
		"bad version hex": {OK: true, Rows: [][]*guest.Cell{{identityCell("42"), {Hex: "zz"}}}},
		"bad id":          {OK: true, Rows: [][]*guest.Cell{{identityCell("bad"), identityCell("12.3.3")}}},
		"overflow id":     {OK: true, Rows: [][]*guest.Cell{{identityCell("4294967296"), identityCell("12.3.3")}}},
	}
	for name, r := range tests {
		t.Run(name, func(t *testing.T) {
			id, version, err := connectionIdentity(r)
			if err == nil || id != 0 || version != nil {
				t.Fatalf("invalid response accepted or fallback provided: %d %q %v", id, version, err)
			}
		})
	}
}
