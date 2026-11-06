//go:build (darwin && arm64) || (linux && amd64)

package generatedgo

import (
	"github.com/masahitojp/mariamem/benchmarks/staticimage"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
)

var staticImageEnabled = os.Getenv("MARIAMEM_STATIC_IMAGE_EXPERIMENT") == "1"
var experimentImage = staticimage.NewEngineFactory(os.TempDir())

func newImageModule(h *host) (*base.Module, func() error, error) {
	m, release, e := experimentImage.AcquireForHost(h, h)
	if e != nil {
		return nil, nil, e
	}
	installGuestThreadLifetime(m)
	return m, release, nil
}
func StaticImageExperimentClose() error { return experimentImage.Close() }
func StaticImageExperimentStats() map[string]any {
	v := experimentImage.Stats()
	v["enabled"] = staticImageEnabled
	return v
}
