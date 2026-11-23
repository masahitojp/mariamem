package snapshot

import (
	"errors"
	"os"
	"runtime"
	"syscall"
	"unsafe"
)

var snapshotKernel = syscall.NewLazyDLL("kernel32.dll")
var snapshotStandardInfo = snapshotKernel.NewProc("GetFileInformationByHandleEx")
var snapshotQueryObject = syscall.NewLazyDLL("ntdll.dll").NewProc("NtQueryObject")

func openSnapshotFile(name string) (*os.File, error) {
	p, err := syscall.UTF16PtrFromString(name)
	if err != nil {
		return nil, err
	}
	// Do not traverse a final reparse point. Sharing deletion allows removal of
	// the implementation-owned pathname while the read-only handle stays live.
	h, err := syscall.CreateFile(p, syscall.GENERIC_READ,
		syscall.FILE_SHARE_READ|syscall.FILE_SHARE_DELETE, nil, syscall.OPEN_EXISTING,
		syscall.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if err != nil {
		return nil, err
	}
	var info syscall.ByHandleFileInformation
	if err = syscall.GetFileInformationByHandle(h, &info); err != nil {
		syscall.CloseHandle(h)
		return nil, err
	}
	if info.FileAttributes&(syscall.FILE_ATTRIBUTE_REPARSE_POINT|syscall.FILE_ATTRIBUTE_DIRECTORY) != 0 {
		syscall.CloseHandle(h)
		return nil, errors.New("snapshot contains reparse point or directory")
	}
	return os.NewFile(uintptr(h), name), nil
}

func snapshotUnlinked(f *os.File, _ os.FileInfo) bool {
	// FILE_STANDARD_INFO: fail closed if the filesystem cannot prove deletion
	// pending with no surviving hard link.
	var info struct {
		AllocationSize int64
		EndOfFile      int64
		NumberOfLinks  uint32
		DeletePending  uint8
		Directory      uint8
		Padding        [2]byte
	}
	ok, _, _ := snapshotStandardInfo.Call(f.Fd(), 1, uintptr(unsafe.Pointer(&info)), unsafe.Sizeof(info))
	runtime.KeepAlive(f)
	return ok != 0 && info.DeletePending != 0 && info.NumberOfLinks == 0 && info.Directory == 0
}
func snapshotCloseOnExec(fd int) error {
	return syscall.SetHandleInformation(syscall.Handle(fd), syscall.HANDLE_FLAG_INHERIT, 0)
}
func snapshotReadOnly(fd int) (bool, error) {
	// PUBLIC_OBJECT_BASIC_INFORMATION is the documented ObjectBasicInformation
	// result. Check actual granted rights, rather than trusting the sender.
	var info struct {
		Attributes, GrantedAccess, HandleCount, PointerCount uint32
		Reserved                                             [10]uint32
	}
	var n uint32
	status, _, _ := snapshotQueryObject.Call(uintptr(fd), 0, uintptr(unsafe.Pointer(&info)), unsafe.Sizeof(info), uintptr(unsafe.Pointer(&n)))
	if int32(status) < 0 {
		return false, errors.New("cannot inspect inherited handle access")
	}
	const fileReadData = 1
	const writable = 2 | 4 | 16 | 256 // data, append, extended attributes, attributes
	return info.GrantedAccess&fileReadData != 0 && info.GrantedAccess&writable == 0, nil
}
