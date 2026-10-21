package mysqlwire

// preparedWireFlags undoes the C client's derived NUM_FLAG for numeric types.
// Pinned libmysqld/lib_sql.cc adds it after copying server_field.flags;
// the network protocol serializes server_field.flags before that augmentation.
// Keep the predicate identical to include/mysql.h's IS_NUM for this fixed guest,
// including NULL (6). Preserve every other flag and all nonnumeric field flags.
func preparedWireFlags(fieldType uint8, flags uint16) uint16 {
	if (fieldType <= 9 && fieldType != 7) || fieldType == 13 || fieldType == 246 {
		return flags &^ 0x8000
	}
	return flags
}
