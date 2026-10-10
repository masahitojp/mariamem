//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"testing"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// The same SQL/driver probes a native comparison server when explicitly supplied.
// Metadata is evidence, not a promise of full MySQL compatibility.
func TestRepresentativeTypes(t *testing.T) {
	ctx := context.Background()
	dsn := os.Getenv("MARIAMEM_TYPE_DSN")
	if dsn == "" {
		if os.Getenv("MARIAMEM_TEST_DEFAULT") != "1" {
			t.Skip("requires real host")
		}
		db, err := mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			t.Fatal(err)
		}
		defer db.Close()
		dsn = db.DSN()
	}
	p, err := sql.Open("mysql", dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()
	_, err = p.ExecContext(ctx, `CREATE TABLE type_probe(i INT,b BIGINT UNSIGNED,f FLOAT,d DOUBLE,n DECIMAL(12,3),day DATE,dt DATETIME,ts TIMESTAMP,v VARCHAR(32),txt TEXT,blobval BLOB,bin BINARY(4),bits BIT(8),nullable INT NULL) ENGINE=InnoDB`)
	if err != nil {
		t.Fatal(err)
	}
	defer p.ExecContext(ctx, "DROP TABLE type_probe")
	if _, err = p.ExecContext(ctx, "SET time_zone='+00:00'"); err != nil {
		t.Fatal(err)
	}
	_, err = p.ExecContext(ctx, `INSERT INTO type_probe VALUES(-7,18446744073709551615,1.25,2.5,123.450,'2026-10-01','2026-10-01 03:04:05','2026-10-01 03:04:05','日本語','text',X'00FF',X'01020304',b'10100101',NULL)`)
	if err != nil {
		t.Fatal(err)
	}
	rows, err := p.QueryContext(ctx, "SELECT * FROM type_probe")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	cols, err := rows.ColumnTypes()
	if err != nil {
		t.Fatal(err)
	}
	if !rows.Next() {
		t.Fatalf("missing row: %v", rows.Err())
	}
	values := make([]any, len(cols))
	ptrs := make([]any, len(cols))
	for i := range values {
		ptrs[i] = &values[i]
	}
	if err = rows.Scan(ptrs...); err != nil {
		t.Fatal(err)
	}
	want := []string{"-7", "18446744073709551615", "1.25", "2.5", "123.450", "2026-10-01", "2026-10-01 03:04:05", "2026-10-01 03:04:05", "日本語", "text", "00ff", "01020304", "a5", "<nil>"}
	record := []map[string]any{}
	for i, v := range values {
		text := fmt.Sprint(v)
		if b, ok := v.([]byte); ok {
			if i >= 10 && i <= 12 {
				text = fmt.Sprintf("%x", b)
			} else {
				text = string(b)
			}
		}
		if text != want[i] {
			t.Errorf("%s=%q want %q", cols[i].Name(), text, want[i])
		}
		length, hasLength := cols[i].Length()
		prec, scale, hasDecimal := cols[i].DecimalSize()
		nullable, hasNullable := cols[i].Nullable()
		record = append(record, map[string]any{"name": cols[i].Name(), "value": text, "go_type": fmt.Sprintf("%T", v), "database_type": cols[i].DatabaseTypeName(), "length": length, "has_length": hasLength, "precision": prec, "scale": scale, "has_decimal": hasDecimal, "nullable": nullable, "has_nullable": hasNullable})
	}
	if rows.Next() || rows.Err() != nil {
		t.Fatal("unexpected row/error")
	}
	b, err := json.Marshal(record)
	if err != nil {
		t.Fatal(err)
	}
	t.Log(string(b))
}
