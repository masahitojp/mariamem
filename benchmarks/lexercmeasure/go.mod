module github.com/masahitojp/mariamem/benchmarks/lexercmeasure

go 1.27.0

require (
 github.com/masahitojp/mariamem v0.6.2
 github.com/masahitojp/mariamem/benchmarks/lexercandidate v0.0.0
 github.com/go-sql-driver/mysql v1.9.3
)
require filippo.io/edwards25519 v1.1.0 // indirect
replace github.com/masahitojp/mariamem => ../..
replace github.com/masahitojp/mariamem/benchmarks/lexercandidate => ../lexercandidate
