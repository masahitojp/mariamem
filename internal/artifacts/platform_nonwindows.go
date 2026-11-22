//go:build !windows

package artifacts

import "errors"

func windowsTarget() (string, int, error) {
	return "", 0, errors.New("Windows platform check on non-Windows host")
}
