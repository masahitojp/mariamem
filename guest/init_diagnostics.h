/* Internal opt-in benchmark hooks. Not a guest protocol or public API. */
#ifndef MARIAMEM_INIT_DIAGNOSTICS_H
#define MARIAMEM_INIT_DIAGNOSTICS_H
#if defined(__wasi__)
#ifdef __cplusplus
extern "C" {
#endif
void mariamem_init_mark(const char *name);
#ifdef __cplusplus
}
#endif
#else
#define mariamem_init_mark(name) ((void)0)
#endif
#endif
