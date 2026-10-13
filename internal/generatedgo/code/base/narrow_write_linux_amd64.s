#include "textflag.h"
TEXT ·atomicWrite8At(SB), NOSPLIT, $0-12
 MOVQ p+0(FP), BX
 MOVL v+8(FP), AX
 XCHGB AX, (BX)
 RET
TEXT ·atomicWrite16At(SB), NOSPLIT, $0-12
 MOVQ p+0(FP), BX
 MOVL v+8(FP), AX
 XCHGW AX, (BX)
 RET
TEXT ·atomicCmp8At(SB), NOSPLIT, $0-20
 MOVQ p+0(FP), BX
 MOVL expected+8(FP), AX
 MOVL replacement+12(FP), CX
 LOCK
 CMPXCHGB CX, (BX)
 MOVBLZX AX, AX
 MOVL AX, ret+16(FP)
 RET
TEXT ·atomicCmp16At(SB), NOSPLIT, $0-20
 MOVQ p+0(FP), BX
 MOVL expected+8(FP), AX
 MOVL replacement+12(FP), CX
 LOCK
 CMPXCHGW CX, (BX)
 MOVWLZX AX, AX
 MOVL AX, ret+16(FP)
 RET
