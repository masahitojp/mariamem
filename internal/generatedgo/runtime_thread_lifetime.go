// Handwritten binding for the accepted guest's allocator and worker entry ABI.
package generatedgo

import (
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/p3"
)

func installGuestThreadLifetime(m *base.Module) {
	base.InstallThreadLifetime(m, p3.Fn153)
}
