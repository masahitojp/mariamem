package mariamem

import "github.com/masahitojp/mariamem/internal/guest"

// Experiment-only counters; not a proposed public API.
func ExperimentTransportBegin()                        { guest.ExperimentBegin() }
func ExperimentTransportEnd() map[string]map[int]int64 { return guest.ExperimentEnd() }
