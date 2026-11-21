module github.com/masahitojp/mariamem/benchmarks

go 1.26.0

require (
    github.com/go-sql-driver/mysql v1.10.1
    github.com/masahitojp/mariamem v0.6.2
)

require filippo.io/edwards25519 v1.2.0 // indirect

replace github.com/masahitojp/mariamem => ..
