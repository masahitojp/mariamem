package mysqlwire

import (
	"encoding/hex"
	"testing"
)

func TestSpikeNativeParameterDescriptor(t *testing.T) {
	// Actual descriptor from pinned MariaDB 12.3.3 native PREPARE, recorded in
	// native-prepare-metadata.json. This checks our limited ordinary-parameter
	// representation, not stored-procedure OUT metadata or all statements.
	want, _ := hex.DecodeString("03646566000000013f000c3f0000000000068000000000")
	if got := hex.EncodeToString(spikeColumn(spikeParameter())); got != hex.EncodeToString(want) {
		t.Fatalf("parameter descriptor %s", got)
	}
}
