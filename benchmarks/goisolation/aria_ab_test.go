package main

import (
	"errors"
	"testing"
)

func TestAriaFixtureStatementFitsPublicSQLLimit(t *testing.T) {
	// Budget includes worst-case string escaping and uint64 text conversion,
	// with the last batch's longest fixture IDs. The SQL path accepts <=1 MiB.
	query, args, _ := ariaFixtureBatch(24000 - ariaFixtureBatchRows)
	bytes := len(query)
	for _, arg := range args {
		switch value := arg.(type) {
		case string:
			bytes += 2*len(value) + 2
		case int:
			bytes += 20
		default:
			t.Fatalf("unbudgeted argument type %T", arg)
		}
	}
	if bytes > 1<<20 {
		t.Fatalf("Aria setup INSERT can exceed SQL/wire limit: %d bytes", bytes)
	}
}

func TestAriaCounterAvailability(t *testing.T) {
	valid := resource{RSS: 200, Primary: 100, CPU: 0.1}
	c, err := sumResources(map[string]resource{"1": valid})
	if err != nil || c.Primary != 100 {
		t.Fatalf("valid counters: %+v %v", c, err)
	}
	for _, transient := range []resource{{RSS: 0, Primary: 0}, {Error: "process counters unavailable"}} {
		c, err = sumResources(map[string]resource{"1": valid, "2": transient})
		if !errors.Is(err, errCountersUnavailable) {
			t.Fatalf("missing counters must be rejected: %v", err)
		}
		if len(c.Members) != 2 {
			t.Fatal("gap diagnostics lost")
		}
	}
	_, err = sumResources(map[string]resource{"1": {Primary: -1, RSS: 200}})
	if err == nil || errors.Is(err, errCountersUnavailable) {
		t.Fatalf("invalid counters must fail, not become a transient gap: %v", err)
	}
}
