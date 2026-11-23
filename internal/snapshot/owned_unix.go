//go:build !windows

package snapshot

import (
	"os"
	"syscall"
)

func openSnapshotFile(name string) (*os.File, error) {
	fd, err := syscall.Open(name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(fd), name), nil
}
func snapshotUnlinked(_ *os.File, st os.FileInfo) bool {
	return st.Sys().(*syscall.Stat_t).Nlink == 0
}
func snapshotCloseOnExec(fd int) error { syscall.CloseOnExec(fd); return nil }
func snapshotReadOnly(fd int) (bool, error) {
	flags, _, errno := syscall.Syscall(syscall.SYS_FCNTL, uintptr(fd), syscall.F_GETFL, 0)
	if errno != 0 {
		return false, errno
	}
	return flags&syscall.O_ACCMODE == syscall.O_RDONLY, nil
}
