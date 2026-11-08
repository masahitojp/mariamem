module github.com/masahitojp/mariamem/benchmarks/issue88modelcase

go 1.27.0

require (
	github.com/go-sql-driver/mysql v1.9.3
	github.com/jackc/pgx/v5 v5.11.0
	github.com/masahitojp/mariamem v0.6.2
	github.com/shibukawa/pgmem v1.18.2
)

require (
	filippo.io/edwards25519 v1.1.0 // indirect
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	github.com/klauspost/compress v1.20.0 // indirect
	golang.org/x/crypto v0.42.0 // indirect
	golang.org/x/sync v0.17.0 // indirect
	golang.org/x/sys v0.44.0 // indirect
	golang.org/x/text v0.29.0 // indirect
)

replace github.com/masahitojp/mariamem => ../..

replace github.com/shibukawa/pgmem => ../../../temp/pgmem
