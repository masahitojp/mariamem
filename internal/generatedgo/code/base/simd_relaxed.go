package base

import "math"

// Relaxed SIMD permits either fused or separately rounded multiply/add.
// Choose the fused projection consistently for both lanes on every platform.
func Simd_f64x2_relaxed_madd(a, b, c [2]uint64) (r [2]uint64) {
	for i := range r {
		r[i] = math.Float64bits(math.FMA(math.Float64frombits(a[i]), math.Float64frombits(b[i]), math.Float64frombits(c[i])))
	}
	return
}
