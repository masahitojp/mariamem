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
