TEXT github.com/masahitojp/mariamem/internal/generatedgo/code/base.MemoryEA(SB)
  :0			0x10024db50		f9400b90		MOVD 16(R28), R16
  :0			0x10024db54		eb3063ff		CMP R16, RSP
  :0			0x10024db58		54000309		BLS 24(PC)
  :0			0x10024db5c		f81e0ffe		MOVD.W R30, -32(RSP)
  :0			0x10024db60		f81f83fd		MOVD R29, -8(RSP)
  :0			0x10024db64		d10023fd		SUB $8, RSP, R29
  :0			0x10024db68		f945cc04		MOVD 2968(R0), R4
  :0			0x10024db6c		c8dffc84		LDAR (R4), R4
  :0			0x10024db70		eb01009f		CMP R1, R4
  :0			0x10024db74		54000163		BCC 11(PC)
  :0			0x10024db78		cb010085		SUB R1, R4, R5
  :0			0x10024db7c		eb05005f		CMP R5, R2
  :0			0x10024db80		54000108		BHI 8(PC)
  :0			0x10024db84		8b010040		ADD R1, R2, R0
  :0			0x10024db88		cb000082		SUB R0, R4, R2
  :0			0x10024db8c		eb02007f		CMP R2, R3
  :0			0x10024db90		54000088		BHI 4(PC)
  :0			0x10024db94		f85f83fd		MOVD -8(RSP), R29
  :0			0x10024db98		f84207fe		MOVD.P 32(RSP), R30
  :0			0x10024db9c		d65f03c0		RET
  :0			0x10024dba0		d001e640		ADRP 63741952(PC), R0
  :0			0x10024dba4		910fe000		ADD $1016, R0, R0
  :0			0x10024dba8		b001e221		ADRP 63197184(PC), R1
  :0			0x10024dbac		91084021		ADD $528, R1, R1
  :0			0x10024dbb0		97f8bd80		CALL runtime.gopanic(SB)
  :0			0x10024dbb4		d503201f		NOOP
  :0			0x10024dbb8		a90087e0		STP (R0, R1), 8(RSP)
  :0			0x10024dbbc		a9018fe2		STP (R2, R3), 24(RSP)
  :0			0x10024dbc0		aa1e03e3		MOVD R30, R3
  :0			0x10024dbc4		97f8d35b		CALL runtime.morestack_noctxt.abi0(SB)
  :0			0x10024dbc8		a94087e0		LDP 8(RSP), (R0, R1)
  :0			0x10024dbcc		a9418fe2		LDP 24(RSP), (R2, R3)
  :0			0x10024dbd0		17ffffe0		JMP github.com/masahitojp/mariamem/internal/generatedgo/code/base.MemoryEA(SB)
  :0			0x10024dbd4		00000000		?
  :0			0x10024dbd8		00000000		?
  :0			0x10024dbdc		00000000		?
TEXT github.com/masahitojp/mariamem/internal/generatedgo/code/base.CheckedMemory32(SB)
  :0			0x10024dbe0		f9400b90		MOVD 16(R28), R16
  :0			0x10024dbe4		eb3063ff		CMP R16, RSP
  :0			0x10024dbe8		540002a9		BLS 21(PC)
  :0			0x10024dbec		f81e0ffe		MOVD.W R30, -32(RSP)
  :0			0x10024dbf0		f81f83fd		MOVD R29, -8(RSP)
  :0			0x10024dbf4		d10023fd		SUB $8, RSP, R29
  :0			0x10024dbf8		2a0103e3		MOVW R1, R3
  :0			0x10024dbfc		2a0203e2		MOVW R2, R2
  :0			0x10024dc00		8b020062		ADD R2, R3, R2
  :0			0x10024dc04		f945cc04		MOVD 2968(R0), R4
  :0			0x10024dc08		c8dffc84		LDAR (R4), R4
  :0			0x10024dc0c		eb02009f		CMP R2, R4
  :0			0x10024dc10		540000a3		BCC 5(PC)
  :0			0x10024dc14		aa0303e0		MOVD R3, R0
  :0			0x10024dc18		f85f83fd		MOVD -8(RSP), R29
  :0			0x10024dc1c		f84207fe		MOVD.P 32(RSP), R30
  :0			0x10024dc20		d65f03c0		RET
  :0			0x10024dc24		d001d5a0		ADRP 61562880(PC), R0
  :0			0x10024dc28		910fe000		ADD $1016, R0, R0
  :0			0x10024dc2c		b001d181		ADRP 61018112(PC), R1
  :0			0x10024dc30		91084021		ADD $528, R1, R1
  :0			0x10024dc34		97f8bd5f		CALL runtime.gopanic(SB)
  :0			0x10024dc38		d503201f		NOOP
  :0			0x10024dc3c		f90007e0		MOVD R0, 8(RSP)
  :0			0x10024dc40		29020be1		STPW (R1, R2), 16(RSP)
  :0			0x10024dc44		aa1e03e3		MOVD R30, R3
  :0			0x10024dc48		97f8d33a		CALL runtime.morestack_noctxt.abi0(SB)
  :0			0x10024dc4c		f94007e0		MOVD 8(RSP), R0
  :0			0x10024dc50		29420be1		LDPW 16(RSP), (R1, R2)
  :0			0x10024dc54		17ffffe3		JMP github.com/masahitojp/mariamem/internal/generatedgo/code/base.CheckedMemory32(SB)
  :0			0x10024dc58		00000000		?
  :0			0x10024dc5c		00000000		?
