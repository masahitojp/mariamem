package mariamem

import (
	"context"
	"fmt"
	"net"
	"strconv"
)

// ConnectionInfo is a copy of the endpoint metadata, also available after Close.
type ConnectionInfo struct {
	Host                     string
	Port                     int
	User, Password, Database string
}

// ConnectionInfo returns endpoint metadata for a MySQL client. The metadata
// remains available after Close, but the endpoint is no longer usable.
func (db *Database) ConnectionInfo() ConnectionInfo { return db.info }

// DSN targets go-sql-driver/mysql. Interpolation supports parameters through the
// text protocol; it does not enable server-side prepared statements.
func (db *Database) DSN() string {
	c := db.info
	return fmt.Sprintf("%s:%s@tcp(%s)/%s?interpolateParams=true", c.User, c.Password, net.JoinHostPort(c.Host, strconv.Itoa(c.Port)), c.Database)
}

// DialContext opens a same-process MySQL wire connection to this database.
// Assign it to go-sql-driver/mysql Config.DialFunc for explicit opt-in. Only
// tcp/tcp4 and this database's exact ConnectionInfo endpoint are accepted.
// It does not complete a handshake. The caller owns the returned connection;
// driver deadlines/cancellation govern subsequent I/O. TCP remains available.
func (db *Database) DialContext(ctx context.Context, network, address string) (net.Conn, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	db.mu.Lock()
	defer db.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if err := db.invalidLocked(); err != nil {
		return nil, err
	}
	if db.closed || db.server == nil {
		return nil, hostError(ErrClosed, "closed", true)
	}
	endpoint := net.JoinHostPort(db.info.Host, strconv.Itoa(db.info.Port))
	if (network != "tcp" && network != "tcp4") || address != endpoint {
		return nil, fmt.Errorf("mariamem DialContext requires tcp/tcp4 endpoint %s", endpoint)
	}
	conn, err := db.server.DialContext(ctx)
	wrapped := hostError(err, "dial", false)
	if detail, ok := wrapped.(*HostError); ok {
		detail.Closed = detail.Code == "closed" || detail.Code == "unusable"
	}
	return conn, wrapped
}
