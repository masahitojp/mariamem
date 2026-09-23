package mariamem

import (
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

func (db *Database) ConnectionInfo() ConnectionInfo { return db.info }

// DSN targets go-sql-driver/mysql. Interpolation supports parameters through the
// text protocol; it does not enable server-side prepared statements.
func (db *Database) DSN() string {
	c := db.info
	return fmt.Sprintf("%s:%s@tcp(%s)/%s?interpolateParams=true", c.User, c.Password, net.JoinHostPort(c.Host, strconv.Itoa(c.Port)), c.Database)
}
