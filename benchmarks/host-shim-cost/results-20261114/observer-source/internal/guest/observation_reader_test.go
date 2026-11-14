package guest
import("testing";"context";"bytes";"encoding/binary";"io";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")
type obsChunks struct{b []byte;n int}
func(c *obsChunks)Read(p []byte)(int,error){if len(c.b)==0{return 0,io.EOF};n:=c.n;if n>len(c.b){n=len(c.b)};if n>len(p){n=len(p)};copy(p,c.b[:n]);c.b=c.b[n:];return n,nil}
func obsPacket(id,slot uint32)[]byte{p:=make([]byte,17);binary.LittleEndian.PutUint32(p,13);p[4]=5;binary.LittleEndian.PutUint32(p[5:],id);binary.LittleEndian.PutUint32(p[9:],slot);return p}
func TestObsReaderFrames(t *testing.T){base.ExperimentPhase(true);defer base.ExperimentPhase(false);for _,chunk:=range []int{1,3,100}{for _,label:=range []string{"dbA","dbB"}{o:=base.NewObs(label);r:=&obsReader{Reader:&obsChunks{b:append(obsPacket(7,2),obsPacket(8,2)...),n:chunk},obs:o};if _,e:=io.Copy(io.Discard,r);e!=nil{t.Fatal(e)};if len(o.Events)!=4||o.Events[0].ID!=7||o.Events[2].ID!=8||o.Events[0].Name!="slot:2"{t.Fatal(o.Events)}}}}
func TestObsReaderBadLength(t *testing.T){for _,n:=range []uint32{8,32<<20+10}{t.Run("bad",func(t *testing.T){defer func(){if recover()==nil{t.Fatal("not rejected")}}();b:=make([]byte,17);binary.LittleEndian.PutUint32(b,n);r:=&obsReader{Reader:bytes.NewReader(b),obs:base.NewObs("bad")};io.Copy(io.Discard,r)})}}

type obsBuffer struct{bytes.Buffer}
func(b *obsBuffer)Close()error{return nil}
func TestObsControlWrite(t *testing.T){b:=&obsBuffer{};p:=&Process{in:b,writes:make(chan struct{},1)};if e:=p.write(context.Background(),make([]byte,4));e!=nil||b.Len()!=4{t.Fatal(e,b.Len())}}
