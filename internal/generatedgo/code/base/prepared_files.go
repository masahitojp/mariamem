package base

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)

// Each child owns its tree, descriptors, offsets and private writable views.
// Mappings outlive every memFile/node that could still reference their storage.
// Close only after guest shutdown and joining ALL generated workers.
type PreparedFiles struct{ mappings [][]byte }

func MapPreparedFiles(fsys *MemFS, dir, prefix string) (*PreparedFiles, error) {
	p := &PreparedFiles{}
	err := filepath.WalkDir(dir, func(name string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(dir, name)
		if err != nil {
			return err
		}
		dest := filepath.ToSlash(filepath.Join(prefix, rel))
		if d.IsDir() {
			return fsys.MkdirAll(dest, 0700)
		}
		if !d.Type().IsRegular() {
			return fmt.Errorf("unsupported prepared entry: %s", rel)
		}
		f, err := os.Open(name)
		if err != nil {
			return err
		}
		defer f.Close()
		st, err := f.Stat()
		if err != nil {
			return err
		}
		if !st.Mode().IsRegular() || st.Size() < 0 || int64(int(st.Size())) != st.Size() {
			return fmt.Errorf("invalid prepared file: %s", rel)
		}
		var data []byte
		if st.Size() > 0 {
			data, err = syscall.Mmap(int(f.Fd()), 0, int(st.Size()), syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_PRIVATE)
			if err != nil {
				return err
			}
			p.mappings = append(p.mappings, data)
		}
		opened, err := fsys.OpenFile(dest, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
		if err != nil {
			return err
		}
		opened.Close()
		fsys.mu.Lock()
		node, err := fsys.lookup(dest)
		if err == nil {
			node.data = data
		}
		fsys.mu.Unlock()
		return err
	})
	if err != nil {
		return nil, errors.Join(err, p.Close())
	}
	return p, nil
}
func (p *PreparedFiles) Close() error {
	if p == nil {
		return nil
	}
	var result error
	for _, data := range p.mappings {
		result = errors.Join(result, syscall.Munmap(data))
	}
	p.mappings = nil
	return result
}
