package main

import (
	"sync/atomic"
	"testing"
	"time"
)

func await(t *testing.T, ch <-chan struct{}) {
	t.Helper()
	select {
	case <-ch:
	case <-time.After(5 * time.Second):
		t.Fatal("scheduling did not complete")
	}
}
func TestBarrierDelaysAllUse(t *testing.T) {
	var starts, uses atomic.Int32
	blocked, release, done := make(chan struct{}), make(chan struct{}), make(chan struct{})
	go func() {
		runChildren(4, 4, true, func(i int) {
			if i == 3 {
				close(blocked)
				<-release
			}
			starts.Add(1)
		}, func(int) {
			if starts.Load() != 4 {
				t.Error("SQL before all ready")
			}
			uses.Add(1)
		}, func() {
			if starts.Load() != 4 || uses.Load() != 0 {
				t.Error("barrier did not isolate startup")
			}
		})
		close(done)
	}()
	await(t, blocked)
	if uses.Load() != 0 {
		t.Fatal("use before release")
	}
	close(release)
	await(t, done)
	if uses.Load() != 4 {
		t.Fatal(uses.Load())
	}
}
func TestPipelineAllowsUseDuringOtherStartup(t *testing.T) {
	blocked, used, release, done := make(chan struct{}), make(chan struct{}), make(chan struct{}), make(chan struct{})
	go func() {
		runChildren(4, 4, false, func(i int) {
			if i == 3 {
				close(blocked)
				<-release
			}
		}, func(i int) {
			if i == 0 {
				close(used)
			}
		}, func() {})
		close(done)
	}()
	await(t, blocked)
	await(t, used)
	close(release)
	await(t, done)
}
func TestSerialOrdering(t *testing.T) {
	next := 0
	runChildren(4, 1, false, func(i int) {
		if next != 2*i {
			t.Error("start order")
		}
		next++
	}, func(i int) {
		if next != 2*i+1 {
			t.Error("use order")
		}
		next++
	}, func() {})
	if next != 8 {
		t.Fatal(next)
	}
}
func TestBarrierRejectsInsufficientWorkers(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Error("accepted deadlocking barrier")
		}
	}()
	runChildren(4, 1, true, func(int) {}, func(int) {}, func() {})
}
