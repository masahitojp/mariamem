# B1 gate: mapping reset safety first
Base c680bfe9ccbf80b012fce897c151fe5a7e42d1e3. Test-only base package spike.
Before performance: prove reset contents, grow-zero, epochs, partial-failure ownership,
protection and concurrency. Actual MAP_FIXED failure semantics must be understood;
injected pre-syscall errors do not prove post-failure address ownership.
If correctness is not established, stop before timing and report the concrete gap.
No product modifications or generation changes. Budget 2h work / 90m execution,
12GiB scratch / 12GiB free. Proposed later timing: same image layout,2GiB,
dirty0/1/64MiB,P1/P2,48cycles,3pairs,initial reserve and final drain included.
