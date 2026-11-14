package base

import (
	"errors"
	"syscall"
)

func normalizeNativeError(err error) error {
	// Anonymous-pipe writes use ERROR_NO_DATA when the reader has closed.
	if errors.Is(err, syscall.ERROR_BROKEN_PIPE) || errors.Is(err, syscall.Errno(232)) {
		return errors.Join(syscall.EPIPE, err)
	}
	return err
}
func nativeFileWriteProbe(file File) error {
	_, err := file.Write(nil)
	// A zero-byte write is the existing fd_allocate writability probe.
	// Windows reports ACCESS_DENIED for a read-only handle, rather than EBADF.
	// Do not remap ACCESS_DENIED for general filesystem operations.
	if errors.Is(err, syscall.ERROR_ACCESS_DENIED) {
		return syscall.EBADF
	}
	return err
}
