// Guest build boundary check: exercise a transferred WASM after macOS AOT.
package main

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func main() {
	if len(os.Args) != 2 {
		panic("usage: x86_guest_smoke NATIVE_DIR")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: os.Args[1]})
	if err != nil {
		panic(err)
	}
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		panic(err)
	}
	var one int
	if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil {
		panic(err)
	}
	if one != 1 {
		panic(fmt.Sprintf("SELECT 1 returned %d", one))
	}
	if err := pool.Close(); err != nil {
		panic(err)
	}
	if err := db.Close(); err != nil {
		panic(err)
	}
	fmt.Println("Start, SELECT 1, Close: PASS")
}
