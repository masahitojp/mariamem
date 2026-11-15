// Handwritten runtime ownership adapter; not wasm2go-generated source.
package base

import "errors"

// DescriptorReleaseError owns failed objects. Close on arbitrary File/net.Conn
// implementations is not necessarily retryable; retain them without re-closing.
type DescriptorReleaseError struct {
	resources []*wasiOpen
	cause     error
}

func (e *DescriptorReleaseError) Error() string { return "descriptor release: " + e.cause.Error() }
func (e *DescriptorReleaseError) Unwrap() error { return e.cause }

// CloseDescriptors releases a quiescent instance's remaining logical FDs.
// Call after all guest workers have joined. Stdio belongs to the caller.
func (w *WasiStubs) CloseDescriptors() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	var result error
	for fd, op := range w.fdTable {
		if err := closeWasiOpen(op); err != nil {
			result = errors.Join(result, &DescriptorReleaseError{resources: []*wasiOpen{op}, cause: err})
		}
		delete(w.fdTable, fd)
	}
	return result
}
