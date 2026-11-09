package staticlayout

import (
	"strings"
	"testing"
)

func TestDiscoverIncludesDistantFlagAndPageProjection(t *testing.T) {
	b := make([]byte, 64*1024)
	b[4099] = 9
	b[40000] = 2
	l := Discover(b, []uint64{4}, 123, []bool{true}, map[string]string{"source": strings.Repeat("a", 64)})
	if l.Begin != 4096 || l.End != 40960 {
		t.Fatal(l)
	}
	for _, x := range [][3]uint64{{4096, 4096, 40960}, {16384, 0, 49152}} {
		begin, end, e := l.Bounds(x[0])
		if e != nil || begin != x[1] || end != x[2] {
			t.Fatal(begin, end, e)
		}
	}
	old := l
	b[60000] = 1
	l = Discover(b, old.Globals, old.DataEnd, old.Dropped, old.SourceSHA256)
	if l.End <= old.End || l.MemorySHA256 == old.MemorySHA256 {
		t.Fatal("new distant initialization omitted")
	}
	if l.MatchesState(uint64(len(b)), []uint64{5}, 123, []bool{true}) {
		t.Fatal("wrong globals accepted")
	}
	if l.MatchesState(uint64(len(b)), []uint64{4}, 123, []bool{false}) {
		t.Fatal("wrong segment state accepted")
	}
}
func TestInvalidAndZeroLayout(t *testing.T) {
	l := Discover(make([]byte, 65536), nil, 0, nil, map[string]string{"source": strings.Repeat("b", 64)})
	a, b, e := l.Bounds(16384)
	if e != nil || a != 0 || b != 0 {
		t.Fatal(a, b, e)
	}
	for _, page := range []uint64{0, 3, 131072} {
		if _, _, e := l.Bounds(page); e == nil {
			t.Fatal(page)
		}
	}
	for _, mutate := range []func(*Layout){func(x *Layout) { x.End = x.MemoryBytes + 4096 }, func(x *Layout) { x.Begin = 1 }, func(x *Layout) { x.Version = 2 }, func(x *Layout) { x.MemorySHA256 = "bad" }, func(x *Layout) { x.SourceSHA256 = nil }} {
		c := l
		mutate(&c)
		if c.Validate() == nil {
			t.Fatal(c)
		}
	}
}
