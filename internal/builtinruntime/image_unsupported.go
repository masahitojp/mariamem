//go:build !(darwin && arm64) && !(linux && amd64)

package builtinruntime

import "fmt"

func image() (string, string, error) { return "", "", fmt.Errorf("unsupported generated-Go platform") }
