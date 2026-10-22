package mysqlwire

import (
	"errors"
	"github.com/masahitojp/mariamem/internal/guest"
	"github.com/masahitojp/mariamem/internal/preparedproto"
)

func preparedColumn(c guest.Column) ([]byte, error) {
	var b []byte
	for _, s := range []string{c.Catalog, c.DB, c.Table, c.OrgTable, c.Name, c.OrgName} {
		if len(s) > maxPacket-len(b)-16 {
			return nil, errors.New("prepared column metadata exceeds packet limit")
		}
		b = append(b, lestr([]byte(s))...)
	}
	b = append(b, 12)
	b = append(b, le16(c.Charset)...)
	b = append(b, le32(c.Length)...)
	b = append(b, c.Type)
	b = append(b, le16(preparedWireFlags(c.Type, c.Flags))...)
	b = append(b, c.Decimals, 0, 0)
	if len(b) > maxPacket {
		return nil, errors.New("prepared column metadata exceeds packet limit")
	}
	return b, nil
}
func validatePrepared(r guest.Result, generation uint32) error {
	if r.Version != 2 || r.PreparedVersion != preparedproto.Version || generation == 0 || r.SessionGeneration != generation {
		return errors.New("prepared API/session identity mismatch")
	}
	if r.Results != nil || (!r.OK && (r.Errno == 0 || len(r.SQLState) != 5)) {
		return errors.New("invalid prepared result envelope")
	}
	return nil
}

// preparePackets does not install the mapping: the caller commits ownership only
// after complete metadata validation, and closes the guest handle on failure.
func preparePackets(r guest.Result, generation, wireID uint32) ([][]byte, error) {
	if err := validatePrepared(r, generation); err != nil {
		return nil, err
	}
	if !r.OK {
		return packets(r)
	}
	if r.BinaryRows || r.Rows != nil || wireID == 0 || r.StatementID == 0 || r.ParamCount > 65535 || uint32(len(r.Parameters)) != r.ParamCount || len(r.Columns) > 65535 {
		return nil, errors.New("invalid prepared metadata")
	}
	b := append([]byte{0}, le32(wireID)...)
	b = append(b, le16(uint16(len(r.Columns)))...)
	b = append(b, le16(uint16(r.ParamCount))...)
	b = append(b, 0)
	b = append(b, le16(r.Warnings)...)
	out := [][]byte{b}
	if r.ParamCount != 0 {
		for _, parameter := range r.Parameters {
			column, err := preparedColumn(parameter)
			if err != nil {
				return nil, err
			}
			out = append(out, column)
		}
		out = append(out, eofPacket(r.Status, 0))
	}
	for _, c := range r.Columns {
		column, err := preparedColumn(c)
		if err != nil {
			return nil, err
		}
		out = append(out, column)
	}
	if len(r.Columns) != 0 {
		out = append(out, eofPacket(r.Status, 0))
	}
	return out, nil
}
