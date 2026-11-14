module github.com/masahitojp/mariamem/benchmarks/forkcurrentprobe

go 1.27

require (
 github.com/go-sql-driver/mysql v1.9.3
 github.com/masahitojp/mariamem v0.0.0
)
require filippo.io/edwards25519 v1.1.0 // indirect
replace github.com/masahitojp/mariamem => ../../worktree
