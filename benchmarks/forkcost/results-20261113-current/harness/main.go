package main
import("context";"database/sql";"encoding/json";"errors";"flag";"fmt";"os";"path/filepath";"runtime/pprof";"sync";"time";"github.com/go-sql-driver/mysql";"github.com/masahitojp/mariamem";"github.com/masahitojp/mariamem/internal/timing";"github.com/masahitojp/mariamem/benchmarks/forkcurrentprobe/store")
type child struct{Index int `json:"index"`;ForkMS float64 `json:"fork_ms"`;Oracle bool `json:"oracle"`;Closed bool `json:"closed"`;Traces map[string]timing.Trace `json:"traces,omitempty"`;mu sync.Mutex;s *mariamem.Database}
type report struct{Success bool `json:"success"`;Error string `json:"error,omitempty"`;Parallel int `json:"parallel"`;Traced bool `json:"traced"`;Profile bool `json:"profile"`;Children []*child `json:"children"`;Profiles []string `json:"profiles,omitempty"`;ProfileWindows []float64 `json:"profile_windows_ms,omitempty"`}
func open(d *mariamem.Database)(*sql.DB,error){cfg,e:=mysql.ParseDSN(d.DSN());if e!=nil{return nil,e};cfg.MultiStatements=true;cfg.ClientFoundRows=true;cfg.DialFunc=d.DialContext;c,e:=mysql.NewConnector(cfg);if e!=nil{return nil,e};return sql.OpenDB(c),nil}
func oracle(ctx context.Context,d *mariamem.Database,index int,negative bool)(err error){db,e:=open(d);if e!=nil{return e};defer func(){err=errors.Join(err,db.Close())}();for _,q:=range []struct{table string;want int}{{"categories",20},{"products",500},{"users",1000},{"orders",0},{"order_items",0},{"audit_log",0}}{var n int;if e=db.QueryRowContext(ctx,"SELECT count(*) FROM "+q.table).Scan(&n);e!=nil{return e};want:=q.want;if negative&&index==0&&q.table=="users"{want++};if n!=want{return fmt.Errorf("pristine oracle %s=%d want%d",q.table,n,want)}};_,e=db.ExecContext(ctx,`INSERT INTO categories(name) VALUES (?)`,fmt.Sprintf("fork-probe-%d",index));return e}
func run(ctx context.Context,r *report,waves int,out string,negative bool)(err error){
 os.Unsetenv("MARIAMEM_TIMING_DIR");root,e:=mariamem.Start(ctx,mariamem.Options{});if e!=nil{return e};rootOpen:=true;defer func(){if rootOpen{err=errors.Join(err,root.Close())}}();db,e:=open(root);if e!=nil{return e};if e=store.Migrate(ctx,db);e==nil{e=store.SeedMaster(ctx,db)};e=errors.Join(e,db.Close());if e!=nil{return e};if e=root.WaitDisconnected(ctx);e!=nil{return e};snap,e:=root.Snapshot(ctx,mariamem.SnapshotOptions{MaxForks:8});if e!=nil{return e};rootOpen=false;defer func(){err=errors.Join(err,snap.Close())}()
 if r.Traced{os.Setenv("MARIAMEM_TIMING_DIR",filepath.Dir(out))}
 for wave:=0;wave<waves;wave++{if e=runWave(ctx,r,snap,wave,out,negative);e!=nil{return e}}
 return nil
}
func runWave(ctx context.Context,r *report,snap *mariamem.Snapshot,wave int,out string,negative bool)(err error){
 cs:=make([]*child,8);contexts:=make([]context.Context,8);for i:=range cs{c:=&child{Index:wave*8+i,Traces:map[string]timing.Trace{}};cs[i]=c;r.Children=append(r.Children,c);contexts[i]=timing.WithRecorder(ctx,func(tr timing.Trace){tr.Events=append([]timing.Event(nil),tr.Events...);c.mu.Lock();c.Traces[tr.Operation]=tr;c.mu.Unlock()})}
 defer func(){for _,c:=range cs{if c.s!=nil&&!c.Closed{e:=c.s.Close();if e==nil{c.Closed=true};err=errors.Join(err,e)}}}()
 var file *os.File
 if r.Profile{path:=fmt.Sprintf("%s-wave%d.pprof",out,wave);var e error;file,e=os.Create(path);if e!=nil{return e};if e=pprof.StartCPUProfile(file);e!=nil{file.Close();return e};r.Profiles=append(r.Profiles,path)}
 at:=time.Now();var wg sync.WaitGroup;sem:=make(chan struct{},r.Parallel);errs:=make(chan error,8)
 for i,c:=range cs{wg.Add(1);go func(i int,c *child){defer wg.Done();sem<-struct{}{};defer func(){<-sem}();start:=time.Now();var e error;c.s,e=snap.Fork(contexts[i]);c.ForkMS=float64(time.Since(start).Nanoseconds())/1e6;if e!=nil{errs<-e}}(i,c)}
 wg.Wait();window:=float64(time.Since(at).Nanoseconds())/1e6
 // Profiling stops before any SQL/WaitDisconnected/Close invocation.
 if r.Profile{pprof.StopCPUProfile();if e:=file.Close();e!=nil{errs<-e};r.ProfileWindows=append(r.ProfileWindows,window)}
 close(errs);for e:=range errs{err=errors.Join(err,e)};if err!=nil{return err}
 for _,c:=range cs{if e:=oracle(ctx,c.s,c.Index,negative);e!=nil{err=errors.Join(err,e)}else{c.Oracle=true};e:=c.s.WaitDisconnected(ctx);err=errors.Join(err,e);e=c.s.Close();if e==nil{c.Closed=true};err=errors.Join(err,e)}
 return err
}
func main(){p:=flag.Int("parallel",1,"");waves:=flag.Int("waves",6,"");traced:=flag.Bool("traced",false,"");prof:=flag.Bool("profile",false,"");negative:=flag.Bool("negative",false,"");out:=flag.String("out","","");flag.Parse();if *p!=1&&*p!=8||*waves<1||*out==""||(*traced&&*prof){panic("invalid probe options")};ctx,cancel:=context.WithTimeout(context.Background(),120*time.Second);defer cancel();r:=report{Parallel:*p,Traced:*traced,Profile:*prof};e:=run(ctx,&r,*waves,*out,*negative);r.Success=e==nil;if e!=nil{r.Error=e.Error()};data,err:=json.MarshalIndent(r,"","  ");if err!=nil{panic(err)};if err=os.WriteFile(*out,data,0600);err!=nil{panic(err)};fmt.Printf("success=%v children=%d p=%d traced=%v profile=%v\n",r.Success,len(r.Children),*p,*traced,*prof);if e!=nil{fmt.Fprintln(os.Stderr,e);os.Exit(1)}}
