package main

import (
	"context"
 "encoding/json"
 "os"
 "path/filepath"
 "github.com/masahitojp/mariamem/internal/timing"
	"database/sql"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/lexerprepared/probe"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func wrap(d *mariamem.Database) *probe.Database {
	return &probe.Database{
		Open: func(route string) (*sql.DB, error) {
			if route != "pipe" {
				return nil, fmt.Errorf("unsupported route %s", route)
			}
			cfg, e := mysql.ParseDSN(d.DSN())
			if e != nil {
				return nil, e
			}
			cfg.DialFunc = d.DialContext
			c, e := mysql.NewConnector(cfg)
			if e != nil {
				return nil, e
			}
			return sql.OpenDB(c), nil
		},
		Wait: d.WaitDisconnected, Close: d.Close,
		Snapshot: func(ctx context.Context, p int) (*probe.Snapshot, error) {
			s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: p})
			if e != nil {
				return nil, e
			}
			return &probe.Snapshot{MaxForks: s.MaxForks(), Close: s.Close, Fork: func(ctx context.Context) (*probe.Database, error) {
				c, e := s.Fork(observe(ctx))
				if e != nil {
					return nil, e
				}
				return wrap(c), nil
			}}, nil
		},
	}
}
func main() {
	probe.CleanupStats = base.LPStats
	probe.Main("mariamem", func(ctx context.Context) (*probe.Database, error) {
		d, e := mariamem.Start(observe(ctx), mariamem.Options{})
		if e != nil {
			return nil, e
		}
		return wrap(d), nil
	})
}

// Each child's context owns its trace association, including concurrent P4.
func observe(ctx context.Context) context.Context {
 i,ok:=ctx.Value("forkstages_child").(int)
 dir:=os.Getenv("LC_STAGE_DIR")
 if !ok || dir=="" {return ctx}
 return timing.WithRecorder(ctx,func(t timing.Trace){
  data,e:=json.Marshal(t);if e!=nil{panic(e)}
  name:=filepath.Join(dir,fmt.Sprintf("child-%03d-%s.json",i,t.Operation))
  f,e:=os.OpenFile(name,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600);if e!=nil{panic(e)}
  _,e=f.Write(append(data,'\n'));ce:=f.Close();if e!=nil{panic(e)};if ce!=nil{panic(ce)}
 })
}
