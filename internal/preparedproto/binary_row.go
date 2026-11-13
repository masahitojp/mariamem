package preparedproto

// ValidateBinaryRow checks a borrowed server row without decoding or rebuilding
// its values. Types come from current result metadata, never client bindings.
// The shared value rules deliberately match EncodeBinaryRow, including NULLs.
func ValidateBinaryRow(row []byte, types []ParameterType, limit int) error {
	if len(types) == 0 || len(types) > 65535 || limit < 1 || limit > MaxEnvelope || len(row) > limit {
		return ErrValue
	}
	maskSize := (len(types) + 9) / 8
	if len(row) < 1+maskSize || row[0] != 0 || row[1]&3 != 0 {
		return ErrValue
	}
	used := (len(types) + 2) % 8
	if used != 0 && row[maskSize] & ^byte((1<<uint(used))-1) != 0 {
		return ErrValue
	}
	mask, p := row[1:1+maskSize], row[1+maskSize:]
	for i, t := range types {
		v := Value{ParameterType: t, Null: mask[(i+2)/8]&(1<<uint((i+2)%8)) != 0}
		if !v.Null {
			shape := valueShape(t.Type)
			var n uint64
			switch {
			case shape > 0:
				n = uint64(shape)
			case shape == -1:
				before := len(p)
				var ok bool
				n, p, ok = readLength(p)
				if !ok || before-len(p) != lengthPrefixSize(n) {
					return ErrValue
				}
			case shape == -2:
				if len(p) == 0 {
					return ErrValue
				}
				n, p = uint64(p[0]), p[1:]
			default:
				return ErrValue
			}
			if n > uint64(len(p)) {
				return ErrValue
			}
			v.Bytes, p = p[:int(n)], p[int(n):]
		}
		if !validValue(v) {
			return ErrValue
		}
	}
	if len(p) != 0 {
		return ErrValue
	}
	return nil
}
