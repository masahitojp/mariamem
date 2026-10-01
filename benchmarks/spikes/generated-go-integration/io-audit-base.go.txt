package base

import "fmt"

func AuditFD(w *WasiStubs, fd int32) string {
	w.mu.Lock()
	defer w.mu.Unlock()
	op := w.fdTable[fd]
	if op == nil || op.f == nil {
		return "absent"
	}
	st, err := op.f.Stat()
	if err != nil {
		return fmt.Sprint(err)
	}
	return fmt.Sprintf("%s size=%d", op.path, st.Size())
}
