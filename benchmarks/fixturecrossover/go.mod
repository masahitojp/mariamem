module mariamem-diagnostic/fixture-crossover

go 1.26.0

require (
	github.com/go-sql-driver/mysql v1.9.3
	github.com/masahitojp/mariamem v0.4.0
	gorm.io/driver/mysql v1.6.0
	gorm.io/gorm v1.31.1
)

// Diagnostic harness uses this worktree's exact released-tag source.
replace github.com/masahitojp/mariamem => ../..

require (
	filippo.io/edwards25519 v1.1.0 // indirect
	github.com/jinzhu/inflection v1.0.0 // indirect
	github.com/jinzhu/now v1.1.5 // indirect
	golang.org/x/text v0.20.0 // indirect
)
