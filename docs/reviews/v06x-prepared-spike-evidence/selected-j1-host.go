package probe
import("encoding/binary";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")
type host struct{*base.WasiStubs;hook func(*base.Module,int32)}
func (h *host) Futex_wait(m *base.Module, addr, expected, timeout, result int32) int32 {
	if addr < 0 || uint64(addr)+4 > m.MemSize.Load() || addr%4 != 0 || timeout < 0 || uint64(timeout)+16 > m.MemSize.Load() || result < 0 || uint64(result)+1 > m.MemSize.Load() {
		return 21
	}
	duration := int64(-1)
	switch m.Memory[timeout] {
	case 0:
	case 1:
		ns := binary.LittleEndian.Uint64(m.Memory[timeout+8:])
		if ns > uint64(1<<63-1) {
			panic("futex duration overflows Go time.Duration")
		}
		duration = int64(ns)
	default:
		panic("invalid futex OptionTimestamp tag")
	}
	rc := base.AtomicWait32At(m, uint64(addr), expected, duration)
	m.Memory[result] = 1
	if rc == 2 {
		m.Memory[result] = 0
	}
	return 0
}

func (h *host) futexWake(m *base.Module, addr, out, count int32) int32 {
	if addr < 0 || uint64(addr)+4 > m.MemSize.Load() || addr%4 != 0 || out < 0 || uint64(out)+1 > m.MemSize.Load() {
		return 21
	}
	base.AtomicNotify(m, addr, 0, count)
 if h.hook!=nil {h.hook(m,out)}
	m.Memory[out] = 1 // Wasmer 7.4.2 returns true even when no waiter exists.
	return 0
}

func (h *host) Futex_wake(m *base.Module, addr, out int32) int32 { return h.futexWake(m, addr, out, 1) }

func (h *host) Futex_wake_all(m *base.Module, addr, out int32) int32 {
	return h.futexWake(m, addr, out, 1<<31-1)
}

func(h *host) Fd_dup(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Fd_dup2(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Getcwd(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Callback_signal(m *base.Module, l0 int32, l1 int32){panic("unexpected import in bounded join fixture")}
func(h *host) Thread_parallelism(m *base.Module, l0 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Thread_signal(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Thread_exit(m *base.Module, l0 int32){panic("unexpected import in bounded join fixture")}
func(h *host) Path_open2(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int64, l6 int64, l7 int32, l8 int32, l9 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Fd_fdflags_get(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Fd_fdflags_set(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Proc_exit2(m *base.Module, l0 int32){panic("unexpected import in bounded join fixture")}
func(h *host) Proc_id(m *base.Module, l0 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Proc_signals_get(m *base.Module, l0 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Proc_signals_sizes_get(m *base.Module, l0 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_addr_local(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_addr_peer(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_open(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_set_opt_flag(m *base.Module, l0 int32, l1 int32, l2 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_set_opt_time(m *base.Module, l0 int32, l1 int32, l2 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_set_opt_size(m *base.Module, l0 int32, l1 int32, l2 int64) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_get_opt_size(m *base.Module, l0 int32, l1 int32, l2 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_bind(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_connect(m *base.Module, l0 int32, l1 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Sock_send_to(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32{panic("unexpected import in bounded join fixture")}
func(h *host) Resolve(m *base.Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32{panic("unexpected import in bounded join fixture")}