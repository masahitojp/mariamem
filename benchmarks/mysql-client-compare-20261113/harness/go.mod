module github.com/shibukawa/pgmem/bench/modelcase

go 1.27

require (
	github.com/go-sql-driver/mysql v1.9.3
	github.com/masahitojp/mariamem v0.0.0
)

require (
	filippo.io/edwards25519 v1.2.0 // indirect
	github.com/coreos/go-semver v0.3.1 // indirect
	github.com/go-mysql-org/go-mysql v1.16.0 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/klauspost/compress v1.18.6 // indirect
	github.com/pingcap/errors v0.11.5-0.20260310054046-9c8b3586e4b2 // indirect
	github.com/pingcap/log v1.1.1-0.20260227082333-572e590d08f1 // indirect
	github.com/pingcap/tidb/pkg/parser v0.0.0-20260504140133-511dba1dbe17 // indirect
	go.uber.org/atomic v1.11.0 // indirect
	go.uber.org/multierr v1.11.0 // indirect
	go.uber.org/zap v1.28.0 // indirect
	golang.org/x/text v0.36.0 // indirect
	gopkg.in/natefinch/lumberjack.v2 v2.2.1 // indirect
)

replace github.com/masahitojp/mariamem => ../../worktree

replace github.com/go-mysql-org/go-mysql => ../go-mysql
