// Toolchain encoding control: real C++ catch/rethrow plus WASIX setjmp/longjmp.
#include <cstdio>
#include <setjmp.h>
static volatile int input = 7;
static void raise_value() { throw int(input); }
static int unwind_value() {
    try { try { raise_value(); } catch (int v) { if (v == 7) throw; return -1; } }
    catch (int v) { return v; }
    return -2;
}
static jmp_buf jump_buffer;
static void jump() { longjmp(jump_buffer, 9); }
int main() {
    int value = unwind_value();
    int j = setjmp(jump_buffer);
    if (j == 0) jump();
    std::printf("C++ unwind=%d setjmp=%d\n", value, j);
    return value == 7 && j == 9 ? 0 : 1;
}
