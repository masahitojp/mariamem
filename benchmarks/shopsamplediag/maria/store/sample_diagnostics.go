package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"
)

var statusNames = []string{
	"Innodb_buffer_pool_read_requests", "Innodb_buffer_pool_reads", "Innodb_buffer_pool_wait_free",
	"Innodb_buffer_pool_write_requests", "Innodb_buffer_pool_pages_data", "Innodb_buffer_pool_pages_dirty",
	"Innodb_buffer_pool_pages_free", "Innodb_buffer_pool_pages_flushed", "Innodb_pages_read", "Innodb_pages_written",
	"Innodb_log_waits", "Innodb_log_write_requests", "Innodb_log_writes", "Innodb_os_log_written",
	"Opened_tables", "Opened_table_definitions", "Open_tables", "Open_table_definitions",
	"Table_open_cache_hits", "Table_open_cache_misses", "Table_open_cache_overflows",
	"Innodb_row_lock_waits", "Innodb_row_lock_time", "Innodb_rows_inserted", "Innodb_rows_updated",
}
var settingNames = []string{
	"innodb_buffer_pool_size", "innodb_buffer_pool_size_max", "innodb_log_buffer_size",
	"table_open_cache", "table_definition_cache", "innodb_flush_log_at_trx_commit",
	"innodb_read_io_threads", "innodb_write_io_threads", "innodb_purge_threads",
	"innodb_adaptive_hash_index", "innodb_doublewrite", "query_cache_type", "query_cache_size",
	"foreign_key_checks", "unique_checks", "check_constraint_checks", "autocommit",
}

type sampleDiagnostic struct {
	Lane          string               `json:"lane"`
	BodyMS        float64              `json:"body_ms"`
	ProbeBeforeMS float64              `json:"probe_before_ms"`
	ProbeAfterMS  float64              `json:"probe_after_ms"`
	Ops           map[string][]float64 `json:"ops_ms"`
	Before        map[string]string    `json:"status_before"`
	After         map[string]string    `json:"status_after"`
	Settings      map[string]string    `json:"settings"`
	Error         string               `json:"error,omitempty"`
}

var sampleDiags struct {
	sync.Mutex
	Records []*sampleDiagnostic
}

func durationMS(t time.Time) float64 { return float64(time.Since(t)) / 1e6 }
func (d *sampleDiagnostic) timer(kind string) func() {
	t := time.Now()
	return func() { d.Ops[kind] = append(d.Ops[kind], durationMS(t)) }
}
func readVariables(ctx context.Context, db *sql.DB, prefix string, names []string) (map[string]string, error) {
	rows, e := db.QueryContext(ctx, prefix+" WHERE Variable_name IN ('"+strings.Join(names, "','")+"')")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	result := map[string]string{}
	for rows.Next() {
		var k, v string
		if e = rows.Scan(&k, &v); e != nil {
			return nil, e
		}
		result[k] = v
	}
	return result, rows.Err()
}
func WriteSampleDiagnostics(path string) error {
	if path == "" {
		return nil
	}
	sampleDiags.Lock()
	defer sampleDiags.Unlock()
	b, e := json.MarshalIndent(struct {
		StatusNames  []string            `json:"requested_status"`
		SettingNames []string            `json:"requested_settings"`
		Records      []*sampleDiagnostic `json:"records"`
	}{statusNames, settingNames, sampleDiags.Records}, "", "  ")
	if e != nil {
		return e
	}
	return os.WriteFile(path, b, 0644)
}
func LoadSample(ctx context.Context, db *sql.DB, lane string) error {
	if os.Getenv("SAMPLE_DIAG") != "1" {
		return loadSampleOriginal(ctx, db)
	}
	return loadSampleObserved(ctx, db, lane)
}
func loadSampleObserved(ctx context.Context, db *sql.DB, lane string) (err error) {
	d := &sampleDiagnostic{Lane: lane, Ops: map[string][]float64{}}
	probe := time.Now()
	d.Settings, err = readVariables(ctx, db, "SHOW VARIABLES", settingNames)
	if err != nil {
		return err
	}
	d.Before, err = readVariables(ctx, db, "SHOW GLOBAL STATUS", statusNames)
	if err != nil {
		return err
	}
	d.ProbeBeforeMS = durationMS(probe)
	start := time.Now()
	defer func() {
		d.BodyMS = durationMS(start)
		p := time.Now()
		var e error
		d.After, e = readVariables(ctx, db, "SHOW GLOBAL STATUS", statusNames)
		d.ProbeAfterMS = durationMS(p)
		if e != nil && err == nil {
			err = e
		}
		if err != nil {
			d.Error = err.Error()
		}
		sampleDiags.Lock()
		sampleDiags.Records = append(sampleDiags.Records, d)
		sampleDiags.Unlock()
	}()
	done := d.timer("begin")
	tx, err := db.BeginTx(ctx, nil)
	done()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	done = d.timer("prepare_order")
	insOrder, err := tx.PrepareContext(ctx, `INSERT INTO orders(user_id, status) VALUES (?, ?) RETURNING id`)
	done()
	if err != nil {
		return err
	}
	defer func() { stop := d.timer("statement_close"); insOrder.Close(); stop() }()
	done = d.timer("prepare_item")
	insItem, err := tx.PrepareContext(ctx, `INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)`)
	done()
	if err != nil {
		return err
	}
	defer func() { stop := d.timer("statement_close"); insItem.Close(); stop() }()
	done = d.timer("prepare_stock")
	reserve, err := tx.PrepareContext(ctx, `UPDATE products SET stock = stock - ? WHERE id = ?`)
	done()
	if err != nil {
		return err
	}
	defer func() { stop := d.timer("statement_close"); reserve.Close(); stop() }()
	for _, o := range SampleOrders() {
		var id int64
		done = d.timer("order_insert")
		err = insOrder.QueryRowContext(ctx, o.UserID, o.Status).Scan(&id)
		done()
		if err != nil {
			return err
		}
		if id != o.ID {
			return fmt.Errorf("store: sample order %d got id %d; the copy is not fresh", o.ID, id)
		}
		for _, it := range o.Items {
			done = d.timer("item_insert")
			_, err = insItem.ExecContext(ctx, id, it.ProductID, it.Quantity, it.UnitPriceCents)
			done()
			if err != nil {
				return err
			}
			done = d.timer("stock_update")
			_, err = reserve.ExecContext(ctx, it.Quantity, it.ProductID)
			done()
			if err != nil {
				return err
			}
		}
	}
	done = d.timer("commit")
	err = tx.Commit()
	done()
	return err
}
