package main

import "testing"

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
