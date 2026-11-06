package probe

import "testing"

func TestResolveMaxForksIndependentOfWorkers(t *testing.T) {
	for _, c := range []struct{ workers, requested, want int }{{4, 0, 4}, {4, 1, 1}, {4, 2, 2}, {4, 4, 4}, {1, 4, 4}} {
		got, e := resolveMaxForks(c.workers, c.requested)
		if e != nil || got != c.want {
			t.Fatalf("%+v got%d %v", c, got, e)
		}
	}
	for _, c := range [][2]int{{0, 1}, {9, 1}, {4, -1}, {4, 9}} {
		if _, e := resolveMaxForks(c[0], c[1]); e == nil {
			t.Fatal("accepted invalid measurement cap", c)
		}
	}
}
