package artifacts

import "testing"

func TestUbuntuPlatform(t *testing.T) {
	for _, raw := range []string{"ID=ubuntu\nVERSION_ID=24.04", "ID=\"ubuntu\"\nVERSION_ID=\"24.04\""} {
		if err := ubuntuPlatform(raw); err != nil {
			t.Fatal(err)
		}
	}
	for _, raw := range []string{"", "ID=debian\nVERSION_ID=24.04", "ID=ubuntu\nVERSION_ID=22.04"} {
		if ubuntuPlatform(raw) == nil {
			t.Fatal("accepted unsupported release", raw)
		}
	}
}
