module github.com/masahitojp/mariamem/benchmarks/issue123baseline

go 1.27.0

require (
 github.com/go-sql-driver/mysql v1.9.3
 github.com/masahitojp/mariamem v0.6.2
)
require filippo.io/edwards25519 v1.1.0 // indirect

replace github.com/masahitojp/mariamem => ../..
