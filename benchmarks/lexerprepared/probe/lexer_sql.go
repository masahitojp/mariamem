package probe

import (
	"context"
	"database/sql"
	"fmt"
	"sync/atomic"
)

var lexerChecks atomic.Uint64

func lexerSQL(ctx context.Context, c *sql.Conn) error {
	var text, h, n, quote string
	var binary, calc int
	if e := c.QueryRowContext(ctx, "SELECT '日本語', HEX(x'0041'), b'101'+0, N'word', 'a''b'").Scan(&text, &h, &binary, &n, &quote); e != nil {
		return e
	}
	if text != "日本語" || h != "0041" || binary != 5 || n != "word" || quote != "a'b" {
		return fmt.Errorf("literal oracle")
	}
	if e := c.QueryRowContext(ctx, "SELECT 2 /* ; ? */ + 3 -- comment\n").Scan(&calc); e != nil {
		return e
	}
	if calc != 5 {
		return fmt.Errorf("comment oracle")
	}
	stmt, e := c.PrepareContext(ctx, "SELECT CONCAT(?, ?)")
	if e != nil {
		return e
	}
	e = stmt.QueryRowContext(ctx, "A\x00'\\", "日本語").Scan(&text)
	ce := stmt.Close()
	if e != nil {
		return e
	}
	if ce != nil {
		return ce
	}
	if text != "A\x00'\\日本語" {
		return fmt.Errorf("prepared value oracle")
	}
	var old string
	if e = c.QueryRowContext(ctx, "SELECT @@SESSION.sql_mode").Scan(&old); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "SET SESSION sql_mode='NO_BACKSLASH_ESCAPES,ANSI_QUOTES'"); e != nil {
		return e
	}
	if e = c.QueryRowContext(ctx, "SELECT \"v\", 'a\\b' FROM fork_probe WHERE \"id\"=2").Scan(&calc, &text); e != nil {
		return e
	}
	if calc != 2 || text != "a\\b" {
		return fmt.Errorf("sql_mode oracle")
	}
	if _, e = c.ExecContext(ctx, "SET SESSION sql_mode=?", old); e != nil {
		return e
	}
	lexerChecks.Add(1)
	return nil
}
