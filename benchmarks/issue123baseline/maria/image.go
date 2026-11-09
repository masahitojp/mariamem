//go:build issue123image

package main

import (
	"github.com/masahitojp/mariamem/benchmarks/issue123baseline/probe"
	"github.com/masahitojp/mariamem/internal/generatedgo"
)

func init() {
	probe.Finalize = generatedgo.StaticImageExperimentClose
	probe.ImageStats = generatedgo.StaticImageExperimentStats
}
