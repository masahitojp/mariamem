//go:build ownedroot_probe

package prepared

// This probe is excluded from ordinary builds. It deliberately violates the
// private-byte ownership boundary, only for a per-call experimental context.
import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"io"
	"strings"
)

type probeKey struct{}
type RootCorruptionProbe struct {
	Mutate           bool   `json:"mutate"`
	Token            string `json:"-"`
	File             string `json:"file"`
	Offset           int64  `json:"offset"`
	Page             int64  `json:"page"`
	PageType         uint16 `json:"page_type"`
	Before           byte   `json:"before"`
	After            byte   `json:"after"`
	StrictRejected   bool   `json:"strict_rejected"`
	MetadataAccepted bool   `json:"metadata_accepted"`
}

func WithRootCorruptionProbe(ctx context.Context, p *RootCorruptionProbe) context.Context {
	return context.WithValue(ctx, probeKey{}, p)
}
func ProbeBeforeOwn(ctx context.Context, r *Root) error {
	p, _ := ctx.Value(probeKey{}).(*RootCorruptionProbe)
	if p == nil {
		return nil
	}
	var target *FrozenFile
	var original []byte
	matches := 0
	for _, name := range r.Names() {
		if !strings.HasSuffix(name, "checksum_probe.ibd") {
			continue
		}
		f := r.File(name)
		raw := make([]byte, f.Size())
		if _, e := io.ReadFull(io.NewSectionReader(f, 0, f.Size()), raw); e != nil {
			return e
		}
		for at := 0; at < len(raw); {
			i := bytes.Index(raw[at:], []byte(p.Token))
			if i < 0 {
				break
			}
			i += at
			matches++
			p.File = name
			p.Offset = int64(i)
			target = f
			original = raw
			at = i + len(p.Token)
		}
	}
	if matches != 1 {
		return fmt.Errorf("probe token matches=%d, want exactly 1", matches)
	}
	p.Page = p.Offset / 16384
	p.PageType = binary.BigEndian.Uint16(original[p.Page*16384+24 : p.Page*16384+26])
	sum := sha256.Sum256(original)
	// Choose an interior payload byte; no page header, key or checksum is changed.
	p.Offset += int64(len(p.Token) / 2)
	at := p.Offset % BlockSize
	entry, ok := target.data.blocks[p.Offset/BlockSize]
	if !ok || at >= int64(entry.block.valid) {
		return fmt.Errorf("probe payload is not a materialized block")
	}
	p.Before = entry.block.data[at]
	p.After = p.Before
	if p.Mutate {
		entry.block.data[at] ^= 1
		p.After = entry.block.data[at]
	}
	p.MetadataAccepted = r.Check(r.Build()) == nil
	blocks := make([]Block, (target.Size()+BlockSize-1)/BlockSize)
	for i, e := range target.data.blocks {
		blocks[i] = e.block
	}
	hf, e := NewHeapFile(target.Size(), blocks, hex.EncodeToString(sum[:]))
	if e != nil {
		return e
	}
	// Reuse the existing strict verifier with the pre-injection expected digest.
	h, e := NewHeap(r.Build(), r.Dirs(), map[string]*HeapFile{p.File: hf})
	if e != nil {
		return e
	}
	p.StrictRejected = h.Verify(r.Build()) != nil
	return nil
}
