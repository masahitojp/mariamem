package common

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func Connect(ctx context.Context, d *mariamem.Database) (*sql.DB, error) {
	cfg, e := mysql.ParseDSN(d.DSN())
	if e != nil {
		return nil, e
	}
	c, e := mysql.NewConnector(cfg)
	if e != nil {
		return nil, e
	}
	p := sql.OpenDB(c)
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	var one int
	e = p.QueryRowContext(ctx, "SELECT 1").Scan(&one)
	if e == nil && one != 1 {
		e = fmt.Errorf("SELECT1=%d", one)
	}
	if e != nil {
		return nil, errors.Join(e, p.Close())
	}
	return p, nil
}
func Oracle(ctx context.Context, p *sql.DB) error {
	var n, total int
	e := p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(v) FROM fork_probe").Scan(&n, &total)
	if e != nil {
		return e
	}
	if n != 1000 || total != 500500 {
		return fmt.Errorf("pristine oracle: count=%d sum=%d", n, total)
	}
	return nil
}
func Disconnect(ctx context.Context, d *mariamem.Database, p *sql.DB) error {
	e := p.Close()
	return errors.Join(e, d.WaitDisconnected(ctx))
}
func Prepare(ctx context.Context) (sn *mariamem.Snapshot, err error) {
	d, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		return nil, e
	}
	defer func() { err = errors.Join(err, d.Close()) }()
	p, e := Connect(ctx, d)
	if e != nil {
		return nil, e
	}
	defer p.Close()
	if _, e = p.ExecContext(ctx, "CREATE TABLE fork_probe(id INTEGER PRIMARY KEY,v INTEGER NOT NULL)"); e != nil {
		return nil, e
	}
	values := make([]string, 1000)
	for i := range values {
		values[i] = fmt.Sprintf("(%d,%d)", i+1, i+1)
	}
	if _, e = p.ExecContext(ctx, "INSERT INTO fork_probe VALUES "+strings.Join(values, ",")); e != nil {
		return nil, e
	}
	if e = Oracle(ctx, p); e != nil {
		return nil, e
	}
	if e = Disconnect(ctx, d, p); e != nil {
		return nil, e
	}
	return d.Snapshot(ctx, mariamem.SnapshotOptions{})
}
func CheckChild(ctx context.Context, d *mariamem.Database, corrupt bool) error {
	p, e := Connect(ctx, d)
	if e != nil {
		return e
	}
	defer p.Close()
	if corrupt {
		if _, e = p.ExecContext(ctx, "UPDATE fork_probe SET v=-1 WHERE id=1"); e != nil {
			return e
		}
	}
	e = Oracle(ctx, p)
	return errors.Join(e, Disconnect(ctx, d, p))
}
func Context() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), 90*time.Second)
}
