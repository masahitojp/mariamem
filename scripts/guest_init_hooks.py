"""Small, fail-closed source insertions into the pinned embedded-server path."""
from pathlib import Path


HOOKS = {
    'libmysqld/lib_sql.cc': [
        ('  DBUG_ASSERT(mysql_embedded_init == 0);', 'embedded_begin', 'before'),
        ('  if (init_server_components())', 'embedded_options_complete', 'before'),
        ('  mysql_embedded_init= 1;', 'embedded_complete', 'after'),
    ],
    'sql/mysqld.cc': [
        ('  DBUG_ENTER("init_server_components");', 'components_begin', 'after'),
        ('  if (plugin_init(&remaining_argc, remaining_argv,', 'plugins_begin', 'before'),
        ("  plugins_are_initialized= TRUE;  /* Don't separate from init function */", 'plugins_complete', 'after'),
        ('  ha_signal_ddl_recovery_done();', 'ddl_recovery_complete', 'after'),
    ],
    'storage/innobase/handler/ha_innodb.cc': [
        ('\tDBUG_ENTER("innodb_init");', 'innodb_plugin_begin', 'after'),
        ('\terr = srv_start(create_new_db);', 'innodb_parameters_complete', 'before'),
        ('\tsrv_was_started = true;', 'innodb_start_complete', 'before'),
    ],
    'storage/innobase/srv/srv0start.cc': [
        ('\tsrv_boot();', 'innodb_runtime_begin', 'before'),
        ('\tif (buf_pool.create()) {', 'buffer_pool_begin', 'before'),
        ('\tlog_sys.create();', 'buffer_pool_complete', 'before'),
        ('\t/* Check if undo tablespaces and redo log files exist before creating', 'innodb_memory_background_complete', 'before'),
        ('\t/* Create the doublewrite buffer to a new tablespace */', 'innodb_open_recovery_complete', 'before'),
        ('\tsrv_startup_is_before_trx_rollback_phase = false;\n\n\tif (!srv_read_only_mode) {', 'innodb_transactions_complete', 'before'),
        ('\tsrv_is_being_started = false;', 'innodb_background_complete', 'after'),
    ],
}


def instrument(source: Path):
    for relative, hooks in HOOKS.items():
        path = source / relative
        text = path.read_text()
        if 'mariamem_init_mark(' in text:
            raise ValueError(f'initialization diagnostic anchor changed: {relative}: already instrumented')
        for anchor, name, position in hooks:
            if text.count(anchor) != 1:
                raise ValueError(f'initialization diagnostic anchor changed: {relative}: {name}')
            mark = f'  mariamem_init_mark("{name}");'
            replacement = mark + '\n' + anchor if position == 'before' else anchor + '\n' + mark
            text = text.replace(anchor, replacement)
        path.write_text('#include "mariamem_init_diagnostics.h"\n' + text)
    return list(HOOKS)
