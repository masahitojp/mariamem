package base

import "sync/atomic"

var bpRecoveryCount atomic.Int64

func NoteBPRecovery()        { bpRecoveryCount.Add(1) }
func ResetBPRecovery()       { bpRecoveryCount.Store(0) }
func BPRecoveryCount() int64 { return bpRecoveryCount.Load() }
