package artifacts

import (
	"context"
	"testing"
)

func TestWindowsNativePlatform(t *testing.T) {
	if err := ValidatePlatform(context.Background()); err != nil {
		t.Fatal(err)
	}
	_, build, err := currentTarget(context.Background())
	if err != nil || build < 22000 {
		t.Fatal(build, err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := ValidatePlatform(ctx); err == nil {
		t.Fatal("cancelled check accepted")
	}
}
