//go:build (darwin && arm64) || (linux && (amd64 || arm64))
package base
import "syscall"
func narrowProtectReadonly(data []byte) error { return syscall.Mprotect(data,syscall.PROT_READ) }
