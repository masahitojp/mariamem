package host

import (
	"context"
	"errors"
	"io"
	"testing"
	"time"

	"github.com/masahitojp/mariamem/internal/artifacts"
	"github.com/masahitojp/mariamem/internal/diagnostic"
)

func TestStartVerifiedRejectsUnownedFields(t *testing.T) {
	// Even matching-looking fields cannot bypass validation or launch a process.
	bundle := artifacts.Bundle{Dir: t.TempDir(), Runtime: "not-executed", Module: "not-executed", Build: "untrusted"}
	server, err := StartVerified(context.Background(), bundle, t.TempDir(), "", time.Second, io.Discard)
	var detail *diagnostic.Error
	if server != nil || !errors.As(err, &detail) || detail.Code != "artifact_mismatch" || detail.Stage != "artifact_validation" {
		t.Fatalf("%v %v", server, err)
	}
}
