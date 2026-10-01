package base

// resizeMemData changes logical file length while amortizing allocation/copy.
// Caller owns the node's storage and holds MemFS.mu. Storage can be either a Go
// byte slice or a child-owned MAP_PRIVATE view; no base/sibling slice is shared.
func resizeMemData(data []byte, size int64) []byte {
	oldLen := len(data)
	if size <= int64(cap(data)) {
		data = data[:size]
		if size > int64(oldLen) {
			// Shrink/O_TRUNC can leave old bytes in capacity. They must never
			// become visible again through truncate growth or a sparse write.
			clear(data[oldLen:])
		}
		return data
	}
	capacity := cap(data)
	growth := capacity
	if capacity >= 1<<20 {
		growth = capacity / 4 // bound spare capacity for large DB files
	}
	maxInt := int(^uint(0) >> 1)
	if growth > maxInt-capacity {
		capacity = int(size)
	} else {
		capacity += growth
		if int64(capacity) < size {
			capacity = int(size)
		}
	}
	grown := make([]byte, size, capacity)
	copy(grown, data)
	return grown
}
