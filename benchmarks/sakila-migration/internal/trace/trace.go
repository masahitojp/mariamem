package trace

type Phase struct {
	Name string  `json:"name"`
	Case string  `json:"case,omitempty"`
	From float64 `json:"from_ms"`
	To   float64 `json:"to_ms"`
}

type Report struct {
	StartMonoNS  int64             `json:"start_mono_ns"`
	StartNS      int64             `json:"start_ns"`
	Backend      string            `json:"backend"`
	SourceCommit string            `json:"source_commit"`
	Version      string            `json:"version"`
	Image        string            `json:"image,omitempty"`
	Parallel     int               `json:"parallel"`
	Reads        int               `json:"reads"`
	Writes       int               `json:"writes"`
	Settings     map[string]string `json:"settings"`
	TotalMS      float64           `json:"total_ms"`
	Phases       []Phase           `json:"phases"`
}
