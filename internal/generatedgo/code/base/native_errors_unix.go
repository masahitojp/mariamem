//go:build !windows

package base

func normalizeNativeError(err error) error { return err }
func nativeFileWriteProbe(file File) error { _, err := file.Write(nil); return err }
