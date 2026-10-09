// Package prepared describes retained cold-file handles, never running state.
package prepared

// Entry is a borrowed descriptor. The owner pins it until mapping completes.
// No consumer writes the descriptor; each child creates its own MAP_PRIVATE view.
type Entry struct {
	Name      string
	Size      int64
	FD        int
	Directory bool
}
