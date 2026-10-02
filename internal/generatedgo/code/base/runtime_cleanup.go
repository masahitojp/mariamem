// Handwritten runtime ownership adapter; not wasm2go-generated source.
package base

import "errors"

// CloseDescriptors releases a quiescent instance's remaining logical FDs.
// Call after all guest workers have joined. Stdio belongs to the caller.
func (w *WasiStubs) CloseDescriptors() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	var err error
	for fd, op := range w.fdTable {
		err = errors.Join(err, closeWasiOpen(op))
		delete(w.fdTable, fd)
	}
	return err
}
