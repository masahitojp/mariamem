package mariamem

import (
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
)

// Match downloaded candidate provenance to this module's canonical build inputs.
// Release identity itself comes from Go build information, never from this file.
//
//go:embed release/inputs.lock.json
var nativeInputs []byte

func nativeInputHash() string {
	hash := sha256.Sum256(nativeInputs)
	return hex.EncodeToString(hash[:])
}
