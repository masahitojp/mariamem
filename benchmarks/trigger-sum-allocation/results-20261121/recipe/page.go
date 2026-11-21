package pageprobe

/*
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach/mach_time.h>
#include <stdint.h>

typedef struct {
    int before, after, refs_before, refs_after, rc_before, rc_after;
    uint64_t ticks;
} measurement;

static measurement measure(void *address, uint32_t value, int write_word, int query) {
    measurement m = {0};
    mach_vm_address_t page = (mach_vm_address_t)(uintptr_t)address;
    m.before = m.after = -1;
    if (query) m.rc_before = mach_vm_page_query(mach_task_self(), page, &m.before, &m.refs_before);
    uint64_t start = mach_absolute_time();
    if (write_word) *(volatile uint32_t *)address = value;
    __asm__ volatile("dsb ish" ::: "memory");
    m.ticks = mach_absolute_time() - start;
    if (query) m.rc_after = mach_vm_page_query(mach_task_self(), page, &m.after, &m.refs_after);
    return m;
}
*/
import "C"

import (
	"os"
	"syscall"
	"unsafe"
)

type Measurement struct {
	Before, After, RefsBefore, RefsAfter int
	Ticks                                uint64
}

func Measure(address unsafe.Pointer, value int32, write, query int) Measurement {
	m := C.measure(address, C.uint32_t(value), C.int(write), C.int(query))
	if m.rc_before != 0 || m.rc_after != 0 {
		panic("mach_vm_page_query failed")
	}
	return Measurement{int(m.before), int(m.after), int(m.refs_before), int(m.refs_after), uint64(m.ticks)}
}

type Controls struct {
	PageSize     int
	Numer, Denom uint32
	Rows         map[string][]Measurement
}

func check(err error) {
	if err != nil {
		panic(err)
	}
}
func Calibrate() Controls {
	size := os.Getpagesize()
	var t C.mach_timebase_info_data_t
	if C.mach_timebase_info(&t) != 0 {
		panic("mach_timebase_info failed")
	}
	data := Controls{size, uint32(t.numer), uint32(t.denom), map[string][]Measurement{}}
	f, err := os.CreateTemp("", "page-calibration-*")
	check(err)
	defer func() { check(f.Close()); check(os.Remove(f.Name())) }()
	const count = 128
	_, err = f.Write(make([]byte, count*size))
	check(err)
	for _, kind := range []string{"file", "anonymous"} {
		fd, flags := int(f.Fd()), syscall.MAP_PRIVATE
		if kind == "anonymous" {
			fd = -1
			flags |= syscall.MAP_ANON
		}
		buf, err := syscall.Mmap(fd, 0, count*size, syscall.PROT_READ|syscall.PROT_WRITE, flags)
		check(err)
		for i := 0; i < count; i++ {
			off := size * i
			if kind == "file" && buf[off] != 0 {
				panic("calibration input")
			}
			for _, label := range []string{"empty", "first", "second"} {
				write := 1
				if label == "empty" {
					write = 0
				}
				key := kind + "_" + label
				data.Rows[key] = append(data.Rows[key], Measure(unsafe.Pointer(&buf[off]), 42, write, 1))
			}
			if buf[off] != 42 {
				panic("calibration store")
			}
		}
		check(syscall.Munmap(buf))
	}
	return data
}
