package base
import "unsafe"
func narrowProtectReadonly(data []byte) error {
    var old uint32
    ok, _, err := memoryKernel.NewProc("VirtualProtect").Call(uintptr(unsafe.Pointer(&data[0])), uintptr(len(data)), 2, uintptr(unsafe.Pointer(&old)))
    if ok == 0 { return err }; return nil
}
