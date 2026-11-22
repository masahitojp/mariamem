//go:build !windows

package base

import "os"

func openPreparedTestBacking(name string) (*os.File, error) { return os.Open(name) }
