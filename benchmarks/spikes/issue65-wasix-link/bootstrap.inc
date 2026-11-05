/* Fresh-only native-wire experiment. Keep the real product bootstrap first. */
int issue65_bootstrap(void)
{
  startup_timing.enabled= getenv("MARIAMEM_GUEST_TIMING") != NULL;
  init_enable();
  mariamem_init_mark("guest_main");
  if (routine_boot_mode(getenv("MARIAMEM_BOOT_MODE"), 0) != 0) return 11;
  if (prepare_auth_keys()) return 18;
  if (l4m_open()) return 11;
  if (!mariamem_auth_keys_ready()) { l4m_close(); return 18; }
  if (routine_bootstrap(g_mysql, 0)) { l4m_close(); return 11; }
  mysql_close(g_mysql);
  g_mysql= NULL;
  mariamem_init_mark("ready_prepared");
  startup_write();
  return 0;
}
void issue65_shutdown(void) { l4m_close(); }
