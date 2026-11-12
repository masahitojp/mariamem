# Current generated read-wait anchors

No source mutation. Numeric-token comparison is an analysis aid only, never an execution guard.

### baseline internal/generatedgo/code/p6/p6_pure.go:896459

```go
func Fn16624(m *base.Module, l0 int32) {
	mBase := m.M
	_ = mBase
	var v13 int32
	_ = v13
	var v15 int32
	_ = v15
	var v17 int32
	_ = v17
	var v18 int32
	_ = v18
	var v20 int32
	_ = v20
	var v24 int32
	_ = v24
	var v28 int32
	_ = v28
	var v32 int32
	_ = v32
	var v43 int32
	_ = v43
	var v55 int32
	_ = v55
	var v58 int32
	_ = v58
	var v59 int32
	_ = v59
	var v75 int32
	_ = v75
	var v87 int32
	_ = v87
	var v95 int32
	_ = v95
	var v96 int32
	_ = v96
	var v98 int32
	_ = v98
	var v100 int32
	_ = v100
	var v104 int32
	_ = v104
	var v105 int32
	_ = v105
	var v107 int32
	_ = v107
	var v110 int32
	_ = v110
	var v114 int32
	_ = v114
	var v124 int32
	_ = v124
	var v133 int32
	_ = v133
	var v143 int32
	_ = v143
	var v145 int32
	_ = v145
	var v155 int32
	_ = v155
	var v165 int32
	_ = v165
	var v177 int32
	_ = v177
	var v180 int32
	_ = v180
	var v183 int32
	_ = v183
	var v185 int32
	_ = v185
	var v189 int32
	_ = v189
	var v190 int32
	_ = v190
	var v192 int32
	_ = v192
	var v195 int32
	_ = v195
	var v199 int32
	_ = v199
	var v209 int32
	_ = v209
	v13 = l0 + int32(28)
	v15 = l0 + int32(4)
	v17 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, 26988792, 0, 4)))
	v18 = int32(2)
	v20 = base.AtomicRmwAdd32(m, l0, int32(0), v18)
	v24 = v17 * int32(50)
	v28 = v24 & int32(6)
	v32 = v20 + v18
	goto L1
L1:
	;
	if v32&int32(1) != 0 {
		goto L3
	} else {
		goto L4
	}
L2:
	;
	v180 = base.AtomicRmwSub32(m, l0, int32(0), int32(2))
	if base.Ui32(int32(3)) <= base.Ui32(v180) {
		goto L48
	} else {
		goto L49
	}
L3:
	;
	goto L6
L4:
	;
	goto L5
L5:
	;
	v75 = int32(0)
	goto L16
L6:
	;
	v43 = Fn93(m, v15)
	mBase = m.M
	goto L9
L7:
	;
	goto L5
L9:
	;
	v55 = int32(atomic.LoadUint32((*uint32)(unsafe.Add(mBase, base.AtomicEA(m, l0, int32(0), 4)))))
	if v32 == v55 {
		goto L11
	} else {
		goto L12
	}
L10:
	;
	v59 = Fn130(m, v15)
	mBase = m.M
	goto L7
L11:
	;
	v58 = Fn216(m, v13, v15, int32(0))
	mBase = m.M
	goto L14
L12:
	;
	goto L13
L13:
	;
	goto L10
L14:
	;
	goto L9
L15:
	;
	goto L2
L16:
	;
	v87 = base.AtomicRmwCmpxchg32(m, l0, int32(124), v75, v75+int32(1))
	if v87 == v75 {
		goto L15
	} else {
		goto L18
	}
L17:
	;
	if v87 == int32(-2147483648) {
		goto L20
	} else {
		goto L21
	}
L18:
	;
	if int32(0) <= v87 {
		v75 = v87
		goto L16
	} else {
		goto L19
	}
L19:
	;
	goto L17
L20:
	;
	goto L23
L21:
	;
	goto L22
L22:
	;
	if v24 == int32(0) {
		goto L36
	} else {
		goto L37
	}
L23:
	;
	v95 = l0 + int32(4)
	v96 = Fn93(m, v95)
	mBase = m.M
	v98 = l0 + int32(28)
	v100 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v98)), 0, 4)))
	if v100 == int32(0) {
		goto L27
	} else {
		goto L28
	}
L24:
	;
	goto L22
L26:
	;
	v124 = Fn130(m, v95)
	mBase = m.M
	goto L24
L27:
	;
	v104 = Fn217(m, v98, int32(-1))
	mBase = m.M
	goto L26
L28:
	;
	goto L29
L29:
	;
	v105 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v98)), 12, 4)))
	if v105 != 0 {
		goto L30
	} else {
		goto L31
	}
L30:
	;
	v107 = l0 + int32(36)
	goto L33
L31:
	;
	goto L32
L32:
	;
	goto L26
L33:
	;
	v110 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v107)), 0, 4)))
	v114 = base.AtomicRmwCmpxchg32(m, v107, int32(0), v110, v110+int32(1))
	if v110 != v114 {
		goto L33
	} else {
		goto L35
	}
L34:
	;
	Fn89(m, v107, int32(2147483647))
	mBase = m.M
	goto L32
L35:
	;
	goto L34
L36:
	;
	v177 = int32(atomic.LoadUint32((*uint32)(unsafe.Add(mBase, base.AtomicEA(m, l0, int32(0), 4)))))
	v32 = v177
	goto L1
L37:
	;
	if v28 != 0 {
		goto L38
	} else {
		goto L39
	}
L38:
	;
	v133 = v28
	goto L41
L39:
	;
	v145 = v24
	goto L40
L40:
	;
	if base.Ui32(v24) < base.Ui32(int32(8)) {
		goto L36
	} else {
		goto L44
	}
L41:
	;
	v143 = v133 - int32(1)
	if v143 != 0 {
		v133 = v143
		goto L41
	} else {
		goto L43
	}
L42:
	;
	v145 = v24 & int32(-8)
	goto L40
L43:
	;
	goto L42
L44:
	;
	v155 = v145
	goto L45
L45:
	;
	v165 = v155 - int32(8)
	if v165 != 0 {
		v155 = v165
		goto L45
	} else {
		goto L47
	}
L46:
	;
	goto L36
L47:
	;
	goto L46
L48:
	;
	goto L51
L49:
	;
	goto L50
L50:
	;
	return
L51:
	;
	v183 = Fn93(m, v15)
	mBase = m.M
	v185 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v13)), 0, 4)))
	if v185 == int32(0) {
		goto L55
	} else {
		goto L56
	}
L52:
	;
	goto L50
L54:
	;
	v209 = Fn130(m, v15)
	mBase = m.M
	goto L52
L55:
	;
	v189 = Fn217(m, v13, int32(-1))
	mBase = m.M
	goto L54
L56:
	;
	goto L57
L57:
	;
	v190 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v13)), 12, 4)))
	if v190 != 0 {
		goto L58
	} else {
		goto L59
	}
L58:
	;
	v192 = l0 + int32(36)
	goto L61
L59:
	;
	goto L60
L60:
	;
	goto L54
L61:
	;
	v195 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v192)), 0, 4)))
	v199 = base.AtomicRmwCmpxchg32(m, v192, int32(0), v195, v195+int32(1))
	if v195 != v199 {
		goto L61
	} else {
		goto L63
	}
L62:
	;
	Fn89(m, v192, int32(2147483647))
	mBase = m.M
	goto L60
L63:
	;
	goto L62
}```
### baseline internal/generatedgo/code/p8/p8_pure.go:359041

```go
func Fn16787(m *base.Module, l0 int32, l1 int32) {
	mBase := m.M
	_ = mBase
	var v5 int32
	_ = v5
	var v7 int32
	_ = v7
	var v8 int32
	_ = v8
	var v11 int32
	_ = v11
	var v12 int32
	_ = v12
	var v13 int64
	_ = v13
	var v20 int32
	_ = v20
	var v22 int32
	_ = v22
	var v23 int32
	_ = v23
	var v25 int32
	_ = v25
	var v32 int32
	_ = v32
	var v36 int32
	_ = v36
	v5 = m.G0
	if l1 != 0 {
		Fn16583(m)
		mBase = m.M
		v7 = m.ExcPending
		if v7 != 0 {
			m.ExcPending = 0
			m.G0 = v5
			Fn1148(m)
			mBase = m.M
			v32 = m.ExcPending
			if v32 != 0 {
				return
			} else {
				base.Wasm_trap_unreachable()
				for {
				}
			}
		} else {
			v8 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l1)), 1464, 4)))
			Fn13959(m, v8, int32(2))
			mBase = m.M
			v11 = m.ExcPending
			if v11 != 0 {
				m.ExcPending = 0
				m.G0 = v5
				Fn1148(m)
				mBase = m.M
				v32 = m.ExcPending
				if v32 != 0 {
					return
				} else {
					base.Wasm_trap_unreachable()
					for {
					}
				}
			} else {
				v12 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l1)), 1468, 4)))
				if v12 != 0 {
					v13 = *(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v12)), 16, 8)))
					*(*int64)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(v12)), 16, 8))) = v13 + int64(1)
				} else {
				}
				Fn16624(m, l0+int32(24))
				mBase = m.M
				v20 = m.ExcPending
				if v20 != 0 {
					m.ExcPending = 0
					m.G0 = v5
					Fn1148(m)
					mBase = m.M
					v32 = m.ExcPending
					if v32 != 0 {
						return
					} else {
						base.Wasm_trap_unreachable()
						for {
						}
					}
				} else {
					Fn16584(m)
					mBase = m.M
					v22 = m.ExcPending
					if v22 != 0 {
						m.ExcPending = 0
						m.G0 = v5
						Fn1148(m)
						mBase = m.M
						v32 = m.ExcPending
						if v32 != 0 {
							return
						} else {
							base.Wasm_trap_unreachable()
							for {
							}
						}
					} else {
						v23 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l1)), 1464, 4)))
						Fn13960(m, v23)
						mBase = m.M
						v25 = m.ExcPending
						if v25 != 0 {
							m.ExcPending = 0
							m.G0 = v5
							Fn1148(m)
							mBase = m.M
							v32 = m.ExcPending
							if v32 != 0 {
								return
							} else {
								base.Wasm_trap_unreachable()
								for {
								}
							}
						} else {
							return
						}
					}
				}
			}
		}
	} else {
		Fn16624(m, l0+int32(24))
		mBase = m.M
		v36 = m.ExcPending
		if v36 != 0 {
			return
		} else {
			return
		}
	}
}```

Candidate exact body hashes are in source-binding.json; its five selected functions have identical non-numeric tokens to the same historical mapping. The duplicate excerpt is omitted.
