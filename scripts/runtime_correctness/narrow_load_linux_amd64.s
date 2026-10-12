#include "textflag.h"
TEXT ·atomicRead8At(SB), NOSPLIT, $0-12
 MOVQ p+0(FP), AX
 MFENCE
 MOVBLZX (AX), CX
 MFENCE
 MOVL CX, ret+8(FP)
 RET
TEXT ·atomicRead16At(SB), NOSPLIT, $0-12
 MOVQ p+0(FP), AX
 MFENCE
 MOVWLZX (AX), CX
 MFENCE
 MOVL CX, ret+8(FP)
 RET
