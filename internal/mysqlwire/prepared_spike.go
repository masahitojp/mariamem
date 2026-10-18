package mysqlwire

// EXPERIMENT ONLY. Bounded non-cursor prepared bridge; unsupported types fail.
import (
	"encoding/binary"
	"encoding/hex"
	"errors"
	"github.com/masahitojp/mariamem/internal/guest"
	"math"
	"strconv"
)

func spikeColumn(c guest.Column) []byte {
	var b []byte
	for _, s := range []string{c.Catalog, c.DB, c.Table, c.OrgTable, c.Name, c.OrgName} {
		b = append(b, lestr([]byte(s))...)
	}
	b = append(b, 12)
	b = append(b, le16(c.Charset)...)
	b = append(b, le32(c.Length)...)
	b = append(b, c.Type)
	b = append(b, le16(c.Flags)...)
	return append(b, c.Decimals, 0, 0)
}

// Placeholder shape must be checked against pinned native 12.3.3. Kept explicit
// rather than pretending the embedded param-metadata API supplied this value.
func spikeParameter() guest.Column {
	return guest.Column{Catalog: "def", Name: "?", Type: 6, Charset: 63, Flags: 128, Length: 0}
}
func spikePrepare(r guest.Result) ([][]byte, error) {
	if !r.OK {
		return packets(r)
	}
	if r.StmtID == 0 || r.ParamCount > 64 || len(r.Columns) > 64 {
		return nil, errors.New("invalid prepared metadata")
	}
	b := append([]byte{0}, le32(r.StmtID)...)
	b = append(b, le16(uint16(len(r.Columns)))...)
	b = append(b, le16(r.ParamCount)...)
	b = append(b, 0)
	b = append(b, le16(r.Warnings)...)
	out := [][]byte{b}
	for i := 0; i < int(r.ParamCount); i++ {
		out = append(out, spikeColumn(spikeParameter()))
	}
	if r.ParamCount != 0 {
		out = append(out, eofPacket(r.Status, 0))
	}
	for _, c := range r.Columns {
		out = append(out, spikeColumn(c))
	}
	if len(r.Columns) != 0 {
		out = append(out, eofPacket(r.Status, 0))
	}
	return out, nil
}
func spikeBinary(r guest.Result) ([][]byte, error) {
	if !r.OK || r.Columns == nil {
		return packets(r)
	}
	out := [][]byte{leint(uint64(len(r.Columns)))}
	for _, c := range r.Columns {
		out = append(out, spikeColumn(c))
	}
	out = append(out, eofPacket(r.Status, 0))
	for _, row := range r.Rows {
		if len(row) != len(r.Columns) {
			return nil, errors.New("binary row width")
		}
		b := make([]byte, 1+(len(row)+9)/8)
		for i, cell := range row {
			if cell == nil {
				b[1+(i+2)/8] |= 1 << uint((i+2)%8)
				continue
			}
			v, err := hex.DecodeString(cell.Hex)
			if err != nil {
				return nil, err
			}
			c := r.Columns[i]
			switch c.Type {
			case 1, 2, 3, 8, 9, 13:
				var n uint64
				if c.Flags&32 != 0 {
					n, err = strconv.ParseUint(string(v), 10, 64)
				} else {
					var s int64
					s, err = strconv.ParseInt(string(v), 10, 64)
					n = uint64(s)
				}
				if err != nil {
					return nil, err
				}
				width := 8
				switch c.Type {
				case 1:
					width = 1
				case 2, 13:
					width = 2
				case 3, 9:
					width = 4
				}
				var buf [8]byte
				binary.LittleEndian.PutUint64(buf[:], n)
				b = append(b, buf[:width]...)
			case 4, 5:
				n, e := strconv.ParseFloat(string(v), 64)
				if e != nil {
					return nil, e
				}
				if c.Type == 4 {
					b = append(b, le32(math.Float32bits(float32(n)))...)
				} else {
					var buf [8]byte
					binary.LittleEndian.PutUint64(buf[:], math.Float64bits(n))
					b = append(b, buf[:]...)
				}
			case 0, 15, 16, 245, 246, 249, 250, 251, 252, 253, 254:
				b = append(b, lestr(v)...)
			default:
				return nil, errors.New("result type outside prepared spike")
			}
		}
		out = append(out, b)
	}
	return append(out, eofPacket(r.Status, r.Warnings)), nil
}
