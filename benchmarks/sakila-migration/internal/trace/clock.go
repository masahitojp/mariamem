package trace

import "golang.org/x/sys/unix"

// MonotonicNS timestamps events on the clock shared by the driver and its child.
func MonotonicNS() int64 {
	var timestamp unix.Timespec
	if err := unix.ClockGettime(unix.CLOCK_MONOTONIC, &timestamp); err != nil {
		panic(err)
	}
	return timestamp.Nano()
}
