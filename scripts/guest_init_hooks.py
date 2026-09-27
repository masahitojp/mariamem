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
        ('  /* call ha_init_key_cache() on all key caches to init them */', 'myisam_key_cache_begin', 'before'),
        ('  process_key_caches(&ha_init_key_cache, 0);', 'myisam_key_cache_complete', 'after'),
        ('  if (plugin_init(&remaining_argc, remaining_argv,', 'plugins_begin', 'before'),
        ("  plugins_are_initialized= TRUE;  /* Don't separate from init function */", 'plugins_complete', 'after'),
        ('  ha_signal_ddl_recovery_done();', 'ddl_recovery_complete', 'after'),
    ],
    'sql/sql_plugin.cc': [
        ('  DBUG_ENTER("plugin_do_initialize");', 'begin', 'plugin_after'),
        ('        print_init_failed_error(plugin);\n      DBUG_RETURN(ret);', 'failed', 'plugin_failure'),
        ('  state= PLUGIN_IS_READY; // plugin->init() succeeded', 'end', 'plugin_before'),
    ],
    'storage/maria/ha_maria.cc': [
        ('  const char *log_dir= maria_data_root;', 'aria_begin', 'after'),
        ('    multi_init_pagecache(&maria_pagecaches, pagecache_segments,', 'aria_cache_begin', 'expression'),
        ('    !init_pagecache(maria_log_pagecache,', 'aria_cache_complete', 'expression'),
        ('    (!aria_readonly &&\n     translog_init(maria_data_root, log_file_size,', 'aria_log_cache_complete', 'expression'),
        ('    (!aria_readonly &&\n     (maria_recovery_from_log() ||', 'aria_log_init_complete', 'expression'),
        ('    ma_checkpoint_init(checkpoint_interval);', 'aria_recovery_complete', 'expression'),
        ('  maria_multi_threaded= maria_in_ha_maria= TRUE;', 'aria_checkpoint_complete', 'before'),
        ('  return res ? HA_ERR_INITIALIZATION : 0;', 'aria_complete', 'before'),
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
        if 'mariamem_init_mark(' in text or 'mariamem_init_plugin_mark(' in text:
            raise ValueError(f'initialization diagnostic anchor changed: {relative}: already instrumented')
        for anchor, name, position in hooks:
            if text.count(anchor) != 1:
                raise ValueError(f'initialization diagnostic anchor changed: {relative}: {name}')
            mark = f'  mariamem_init_mark("{name}");'
            if position.startswith('plugin_'):
                mark = f'  mariamem_init_plugin_mark(plugin->plugin->name, "{name}");'
            if position == 'plugin_failure':
                replacement = anchor.replace('      DBUG_RETURN(ret);', mark + '\n      DBUG_RETURN(ret);')
            elif position == 'expression':
                # Zero is the identity operand of this short-circuit OR chain.
                # Preserve each function call, condition, ordering and failure path.
                replacement = f'    (mariamem_init_mark("{name}"), 0) ||\n' + anchor
            else:
                replacement = mark + '\n' + anchor if position in ('before', 'plugin_before') else anchor + '\n' + mark
            text = text.replace(anchor, replacement)
        path.write_text('#include "mariamem_init_diagnostics.h"\n' + text)
    return list(HOOKS)
