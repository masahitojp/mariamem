package guest
import("io";"strconv";"encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")
type obsReader struct{io.Reader;obs *base.ObsInstance;buf []byte}
func(r *obsReader)Observation()*base.ObsInstance{return r.obs}
func(r *obsReader)Read(b []byte)(int,error){n,e:=r.Reader.Read(b);r.buf=append(r.buf,b[:n]...);for len(r.buf)>=4 {l:=binary.LittleEndian.Uint32(r.buf);if l==0||l==0xfffffffe{r.buf=r.buf[4:];continue};if l>32<<20+9{panic("observer oversize")};if len(r.buf)<int(l)+4{break};if l<9{panic("observer short")};id:=int32(binary.LittleEndian.Uint32(r.buf[5:]));r.obs.Mark(id,"slot:"+strconv.FormatUint(uint64(binary.LittleEndian.Uint32(r.buf[9:])),10));r.obs.Mark(id,"guest_frame");r.buf=r.buf[4+int(l):]};return n,e}
