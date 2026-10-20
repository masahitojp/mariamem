/* Product-managed mysql.proc structure; user routine rows remain mutable.
 * DDL and metadata are generated from the pinned MariaDB source/native contract.
 * Never repair a restored baseline or publish readiness after a failed step.
 */
#include "routine_schema_sql.inc"

static int routine_failure(MYSQL *c, const char *step, const char *reason)
{
  fprintf(stderr, "mariamem: routine_bootstrap step=%s errno=%u sqlstate=%s reason=%s error=%s ddl=%s; "
          "Fresh failure with matching artifacts requires a bootstrap bug report; "
          "an incompatible restored proc structure requires preparing a new baseline.\n",
          step, c ? mysql_errno(c) : 0, c ? mysql_sqlstate(c) : "HY000",
          reason, c ? mysql_error(c) : "no connection", ROUTINE_SCHEMA_DDL_SHA256);
  return -1;
}

static int routine_statement(MYSQL *c, const char *sql, const char *step)
{
  if (mysql_query(c, sql))
    return routine_failure(c, step, "SQL failed");
  return 0;
}

static MYSQL_RES *routine_result(MYSQL *c, const char *sql, const char *step)
{
  if (routine_statement(c, sql, step)) return NULL;
  MYSQL_RES *r= mysql_store_result(c);
  if (!r) routine_failure(c, step, "metadata result missing");
  return r;
}

static int routine_scalar(MYSQL *c, const char *sql, const char *value, const char *step)
{
  MYSQL_RES *r= routine_result(c, sql, step);
  if (!r) return -1;
  MYSQL_ROW row= mysql_fetch_row(r);
  int ok= mysql_num_fields(r) == 1 && mysql_num_rows(r) == 1 && row && row[0] && !strcmp(row[0], value);
  mysql_free_result(r);
  return ok ? 0 : routine_failure(c, step, "unexpected metadata or bootstrap context");
}

static int routine_validate(MYSQL *c)
{
  MYSQL_RES *r= routine_result(c,
    "SELECT COLUMN_NAME,COLUMN_TYPE,COLLATION_NAME,IS_NULLABLE FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc' ORDER BY ORDINAL_POSITION", "columns");
  if (!r) return -1;
  const size_t count= sizeof(routine_schema_columns) / sizeof(routine_schema_columns[0]);
  int ok= mysql_num_fields(r) == 4 && mysql_num_rows(r) == count;
  for (size_t i= 0; ok && i < count; i++)
  {
    MYSQL_ROW row= mysql_fetch_row(r);
    if (!row) { ok= 0; break; }
    for (size_t j= 0; j < 4; j++)
    {
      const char *expected= routine_schema_columns[i][j];
      if ((row[j] == NULL) != (expected == NULL) ||
          (expected && row[j] && strcmp(row[j], expected))) { ok= 0; break; }
    }
  }
  mysql_free_result(r);
  if (!ok) return routine_failure(c, "columns", "incompatible product-managed proc structure; not repaired");
  r= routine_result(c,
    "SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc' "
    "AND INDEX_NAME='PRIMARY' ORDER BY SEQ_IN_INDEX", "primary_key");
  if (!r) return -1;
  const size_t keys= sizeof(routine_schema_key) / sizeof(routine_schema_key[0]);
  ok= mysql_num_fields(r) == 1 && mysql_num_rows(r) == keys;
  for (size_t i= 0; ok && i < keys; i++)
  {
    MYSQL_ROW row= mysql_fetch_row(r);
    if (!row || !row[0] || strcmp(row[0], routine_schema_key[i])) ok= 0;
  }
  mysql_free_result(r);
  if (!ok) return routine_failure(c, "primary_key", "incompatible product-managed proc key; not repaired");
  return routine_scalar(c,
    "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc'",
    routine_schema_engine, "engine");
}

static int routine_boot_mode(const char *mode, int legacy_restore)
{
  if (!mode || (strcmp(mode, "fresh") && strcmp(mode, "restore")) ||
      (legacy_restore && strcmp(mode, "restore")))
    return routine_failure(NULL, "mode", "missing, invalid or contradictory host-authored boot mode");
  return !strcmp(mode, "restore");
}

static int routine_bootstrap(MYSQL *c, int restore)
{
  if (restore != 0 && restore != 1)
    return routine_failure(c, "mode", "invalid boot mode");
  if (restore) return routine_validate(c);

  if (routine_scalar(c, "SELECT DATABASE()", "test", "context") ||
      routine_scalar(c, "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='mysql'", "0", "fresh_state") ||
      routine_statement(c, "SET @mariamem_bootstrap_sql_mode=@@SESSION.sql_mode", "save_sql_mode") ||
      routine_statement(c, "SET SESSION sql_mode=''", "sql_mode") ||
      routine_statement(c, "CREATE DATABASE mysql", "create_schema")) return -1;
  if (mysql_select_db(c, "mysql")) return routine_failure(c, "select_schema", "SQL failed");
  if (routine_statement(c, routine_schema_ddl, "create_proc")) return -1;
  if (mysql_select_db(c, "test")) return routine_failure(c, "restore_database", "SQL failed");
  if (routine_statement(c, "SET SESSION sql_mode=@mariamem_bootstrap_sql_mode", "restore_sql_mode")) return -1;
  /* Charset/collation were never changed. Private user variables die on close. */
  return routine_validate(c);
}
