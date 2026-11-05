package probe

import "testing"

func TestUpdateGuestLabelBinding(t *testing.T) {
	for _, v := range []struct {
		text string
		want bool
	}{
		{"# labels: {\"child\":\"7\"}\n# github.com/masahitojp/mariamem/internal/generatedgo/code/p1.Fn123", true},
		{"# labels: {\"child\":\"6\"}\n# github.com/masahitojp/mariamem/internal/generatedgo/code/p1.Fn123", false},
		{"# labels: {\"child\":\"7\",\"role\":\"client\"}\n# probe.updateObserved", false},
		{"# labels: {bad}\n# github.com/masahitojp/mariamem/internal/generatedgo/code/p1.Fn123", false},
		{"# labels: {\"child\":\"7\"}\n# probe.updateObserved\n\n# labels: {\"child\":\"6\"}\n# github.com/masahitojp/mariamem/internal/generatedgo/code/p1.Fn123", false}} {
		if got := hasGuestLabel([]byte(v.text), "7"); got != v.want {
			t.Fatalf("binding %v want%v", got, v.want)
		}
	}
}

func TestUpdateExecWindow(t *testing.T) {
	for _, v := range []struct {
		m    updateMeta
		want bool
	}{
		{updateMeta{ExecEnterMS: 1, SnapshotBeginMS: 101, SnapshotEndMS: 102, ExecReturnMS: 300}, true},
		{updateMeta{ExecEnterMS: 200, SnapshotBeginMS: 101, SnapshotEndMS: 102, ExecReturnMS: 201}, false},
		{updateMeta{ExecEnterMS: 1, SnapshotBeginMS: 101, SnapshotEndMS: 105, ExecReturnMS: 102}, false},
		{updateMeta{SnapshotBeginMS: 101, SnapshotEndMS: 102, ExecReturnMS: 300}, false}} {
		if profileInsideExec(v.m) != v.want {
			t.Fatal(v)
		}
	}
}
