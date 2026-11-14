package mariamem
import "github.com/masahitojp/mariamem/internal/generatedgo/code/base"
 import "os"
func ExperimentPhase(on bool){base.ExperimentPhase(on)}
func ExperimentDump(path string)error{if err:=base.ObsDump(os.Getenv("OBS_FILE"));err!=nil{return err};return base.ExperimentDump(path)}
 func ExperimentClock()int64{return base.ObsNow()}
