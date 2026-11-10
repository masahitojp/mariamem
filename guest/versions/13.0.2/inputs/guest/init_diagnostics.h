/* Internal opt-in benchmark hooks. Not a guest protocol or public API. */
#ifndef MARIAMEM_INIT_DIAGNOSTICS_H
#define MARIAMEM_INIT_DIAGNOSTICS_H
#if defined(__wasi__)
#ifdef __cplusplus
extern "C" {
#endif
void mariamem_init_mark(const char *name);
void mariamem_init_plugin_mark(const char *name, const char *boundary);
#ifdef __cplusplus
}
#endif
#else
#define mariamem_init_mark(name) ((void)0)
#define mariamem_init_plugin_mark(name, boundary) ((void)0)
#endif
#endif
