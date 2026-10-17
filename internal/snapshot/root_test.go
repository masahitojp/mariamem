package snapshot

import (
	"github.com/masahitojp/mariamem/internal/prepared"
	"os"
	"path/filepath"
	"testing"
)

func TestRootHandoffUsesStrictReceiver(t *testing.T) {
	s := prepared.NewRootSource(true)
	f := prepared.NewFileStore(s)
	input := []byte("original")
	if _, e := f.WriteAt(input, 0); e != nil {
		t.Fatal(e)
	}
	input[0] = 'X'
	image, e := f.Seal()
	if e != nil {
		t.Fatal(e)
	}
	c := &prepared.Capture{}
	if e = c.BindRootSource(s, "guest"); e != nil {
		t.Fatal(e)
	}
	c.Request()
	if e = c.CompleteRoot(s, "guest", []string{"."}, map[string]*prepared.FrozenFile{"f": image}); e != nil {
		t.Fatal(e)
	}
	r, e := c.TakeRoot("guest")
	if e != nil {
		t.Fatal(e)
	}
	o, e := OwnRoot(r, "guest")
	if e != nil {
		t.Fatal(e)
	}
	defer o.Close()
	path := filepath.Join(t.TempDir(), "transfer")
	if e = o.Handoff(path, "guest"); e != nil {
		t.Fatal(e)
	}
	receiver, e := Import(path, "guest")
	if e != nil {
		t.Fatal(e)
	}
	defer receiver.Close()
	entries, release, e := receiver.Acquire("guest")
	if e != nil {
		t.Fatal(e)
	}
	if len(entries) < 2 {
		t.Fatal("missing receiver files")
	}
	release()
	if _, e = Import(path, "other"); e == nil {
		t.Fatal("wrong identity accepted")
	}
	if e = os.WriteFile(filepath.Join(path, "data/f"), []byte("modified"), 0600); e != nil {
		t.Fatal(e)
	}
	if x, e := Import(path, "guest"); e == nil {
		if x != nil {
			x.Close()
		}
		t.Fatal("corrupted handoff accepted")
	}
	p := make([]byte, 8)
	if _, e = r.File("f").ReadAt(p, 0); e != nil || string(p) != "original" {
		t.Fatal("handoff changed source", e)
	}
}
