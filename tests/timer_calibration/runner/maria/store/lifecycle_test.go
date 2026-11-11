package store_test

import (
 "encoding/json"
 "os"
 "time"
 "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

type lifecycleObservation struct {
 Kind string `json:"kind"`
 Wall float64 `json:"wall_ms"`
 CPU float64 `json:"cpu_ms"`
}
func lifecycleBatch() {
 observations:=[]lifecycleObservation{}
 for i:=0;i<8;i++ {
  ctx,cancel:=timeout()
  cpu:=cost();begin:=time.Now()
  owner,err:=startBackend(ctx)
  elapsed:=float64(time.Since(begin))/float64(time.Millisecond); used:=cost()-cpu
  must(err);cancel()
  observations=append(observations,lifecycleObservation{"fresh",elapsed,used})
  db:=owner.open();var one int;must(db.QueryRow("SELECT 1").Scan(&one));if one!=1 {panic("SELECT mismatch")}
  retire(owner,db)
 }
 ctx,cancel:=timeout();root,err:=startBackend(ctx);must(err);cancel()
 db:=root.open();_,err=db.Exec("CREATE TABLE timer_lifecycle(id INT PRIMARY KEY) ENGINE=InnoDB");must(err)
 _,err=db.Exec("INSERT INTO timer_lifecycle VALUES(1)");must(err);must(db.Close());must(root.wait())
 fork,closeSnapshot,err:=root.snapshot();must(err);must(root.close())
 for i:=0;i<16;i++ {
  cpu:=cost();begin:=time.Now();child,err:=fork("lifecycle")
  elapsed:=float64(time.Since(begin))/float64(time.Millisecond);used:=cost()-cpu;must(err)
  observations=append(observations,lifecycleObservation{"fork",elapsed,used})
  p:=child.open();var count int;must(p.QueryRow("SELECT COUNT(*) FROM timer_lifecycle").Scan(&count))
  if count!=1 {panic("Fork baseline changed")}
  _,err=p.Exec("INSERT INTO timer_lifecycle VALUES(?)",i+10);must(err);retire(child,p)
 }
 must(closeSnapshot())
 n:=base.MemoryMappingStats()["active_mappings"];if n!=0 {panic("mapping leak")}
 data,err:=json.Marshal(map[string]interface{}{"result":"PASS","observations":observations,"active_mappings_after":n});must(err)
 must(os.WriteFile(os.Getenv("MODELCASE_TRACE"),data,0644))
}
