#include "textflag.h"
TEXT ·atomicRead8At(SB), NOSPLIT, $0-12
 MOVD p+0(FP), R0
 DMB $0xb
 LDARB (R0), R1
 DMB $0xb
 MOVW R1, ret+8(FP)
 RET
TEXT ·atomicRead16At(SB), NOSPLIT, $0-12
 MOVD p+0(FP), R0
 DMB $0xb
 LDARH (R0), R1
 DMB $0xb
 MOVW R1, ret+8(FP)
 RET
