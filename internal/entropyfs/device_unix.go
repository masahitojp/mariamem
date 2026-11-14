//go:build !windows

package entropyfs

import "os"

func Open(name string) (*os.File, error) {
	if !allowed(name) {
		return nil, os.ErrNotExist
	}
	return os.Open(name)
}
func Stat(name string) (os.FileInfo, error) {
	if !allowed(name) {
		return nil, os.ErrNotExist
	}
	return os.Stat(name)
}
