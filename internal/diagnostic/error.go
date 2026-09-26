// Package diagnostic carries a small failure boundary through internal layers.
package diagnostic

import "fmt"

type Error struct {
	Code, Stage string
	Err         error
}

func (e *Error) Error() string { return fmt.Sprintf("%s: %v", e.Stage, e.Err) }
func (e *Error) Unwrap() error { return e.Err }
func Wrap(code, stage string, err error) error {
	if err == nil {
		return nil
	}
	return &Error{Code: code, Stage: stage, Err: err}
}
