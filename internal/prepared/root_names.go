package prepared

import (
	"errors"
	"path"
)

func checkRootNames(dirs []string, files map[string]*FrozenFile) error {
	valid := func(n string) bool {
		return n != "" && !path.IsAbs(n) && path.Clean(n) == n && n != ".." && !(len(n) >= 3 && n[:3] == "../")
	}
	d := map[string]bool{}
	for _, n := range dirs {
		if !valid(n) || d[n] {
			return errors.New("invalid root directory")
		}
		d[n] = true
	}
	if !d["."] {
		return errors.New("missing root directory")
	}
	for _, n := range dirs {
		if n != "." && !d[path.Dir(n)] {
			return errors.New("missing root directory parent")
		}
	}
	for n, f := range files {
		if !valid(n) || d[n] || !d[path.Dir(n)] || f == nil {
			return errors.New("invalid root file")
		}
	}
	return nil
}
