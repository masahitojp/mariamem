package nativewire

import (
	"encoding/binary"
	"fmt"
	"io"
)

// The envelope is private host/guest control framing, never MySQL framing.
const (
	kindOutputGrant    = 14
	kindOpen           = 1
	kindData           = 2
	kindAck            = 3
	kindPeerEOF        = 4
	kindStop           = 6
	kindReady          = 100
	kindOpened         = 101
	kindRaw            = 103
	kindRetired        = 104
	kindPoison         = 105
	kindCredit         = 106
	kindState          = 107
	kindRejected       = 110
	kindCaptureFence   = 11
	kindCaptureStop    = 12
	kindFenced         = 112
	kindStopAccepted   = 113
	kindCaptureStopped = 114
	inputLimit         = 1048581
)

type frame struct {
	kind                     byte
	request, slot            uint32
	epoch, generation, value uint64
	body                     []byte
}

func readFrame(r io.Reader) (f frame, err error) {
	var h [4]byte
	if _, err = io.ReadFull(r, h[:]); err != nil {
		return
	}
	n := binary.LittleEndian.Uint32(h[:])
	if n < 33 || n > 65569 {
		return f, fmt.Errorf("private frame size %d", n)
	}
	b := make([]byte, n)
	if _, err = io.ReadFull(r, b); err != nil {
		return
	}
	f = frame{b[0], binary.LittleEndian.Uint32(b[1:]), binary.LittleEndian.Uint32(b[5:]), binary.LittleEndian.Uint64(b[9:]), binary.LittleEndian.Uint64(b[17:]), binary.LittleEndian.Uint64(b[25:]), b[33:]}
	return
}
func writeFrame(w io.Writer, f frame) error {
	b := make([]byte, 37+len(f.body))
	binary.LittleEndian.PutUint32(b, uint32(len(b)-4))
	b[4] = f.kind
	binary.LittleEndian.PutUint32(b[5:], f.request)
	binary.LittleEndian.PutUint32(b[9:], f.slot)
	binary.LittleEndian.PutUint64(b[13:], f.epoch)
	binary.LittleEndian.PutUint64(b[21:], f.generation)
	binary.LittleEndian.PutUint64(b[29:], f.value)
	copy(b[37:], f.body)
	for len(b) > 0 {
		n, e := w.Write(b)
		if e != nil {
			return e
		}
		if n <= 0 || n > len(b) {
			return io.ErrNoProgress
		}
		b = b[n:]
	}
	return nil
}
