package main

import (
	"context"
	"errors"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/masahitojp/mariamem"
)

// One prepared fixture and identical canonical batch/readiness/cleanup code.
// Environment changes happen only between fully closed batches, never per DB.
func (r *runner) restoreComparison() (err error) {
	if !r.cfg.stages || !r.cfg.guestStages || r.cfg.memoryDiagnostics {
		return errors.New("restore A/B requires guest stage timing and excludes memory diagnostics")
	}
	previous, existed := os.LookupEnv("MARIAMEM_EXPERIMENT_RESTORE")
	defer func() {
		if existed {
			os.Setenv("MARIAMEM_EXPERIMENT_RESTORE", previous)
		} else {
			os.Unsetenv("MARIAMEM_EXPERIMENT_RESTORE")
		}
	}()
	os.Setenv("MARIAMEM_EXPERIMENT_RESTORE", "stdio")
	db, row, err := r.startup(nil, time.Now())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, db.Close()) }()
	r.version = row["server_version"].(string)
	if err = r.seed(db); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, saved.Close()) }()
	if !db.Closed() {
		return errors.New("snapshot did not consume source")
	}
	inventory := snapshotDiagnostics(saved.Path())
	for _, text := range strings.Split(r.cfg.workers, ",") {
		workers, _ := strconv.Atoi(text)
		for round := 0; round < r.cfg.warmup+r.cfg.runs; round++ {
			order := []string{"stdio", "direct"}
			if round%2 == 1 {
				order[0], order[1] = order[1], order[0]
			}
			for position, mode := range order {
				os.Setenv("MARIAMEM_EXPERIMENT_RESTORE", mode)
				value, e := r.batch(saved, workers)
				if e != nil {
					return e
				}
				value["case"] = "fork_first_sql"
				value["condition"] = mode
				value["snapshot_inventory"] = inventory
				value["workers"] = workers
				value["run"] = round
				value["order_position"] = position
				value["phase"] = "measurement"
				if round < r.cfg.warmup {
					value["phase"] = "warmup"
				}
				r.samples = append(r.samples, value)
			}
		}
	}
	return nil
}
