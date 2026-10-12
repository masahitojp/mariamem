"""Verify pinned sources and retain compact anchors for manual protocol review."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SELECT = {
 "runtime": {
  "internal/generatedgo/runtime_instance.go": r"StartInstance|executeGuest|WaitThreads|defer releaseMemoryModule|exportTransfer|CloseDescriptors",
  "internal/generatedgo/memory_lifetime.go": r"WaitThreads|release\(\)|KeepAlive",
  "internal/generatedgo/main.go": r"func \(h \*host\)|AtomicWait32At|AtomicNotify|signalCallback =|ThreadLaunch",
  "internal/generatedgo/code/base/base.go": r"func ThreadLaunch|func ThreadSpawn|nextTID.Add|func \(p \*ThreadPool\) WaitThreads|wg.Wait|cmd.Wait\(\)|proc.status =|close\(proc.done\)",
 },
 "mariadb": {
  "tpool/tpool_generic.cc": r"worker_main|worker_end|add_thread|~thread_pool_generic|disarm\(|m_cv_no_threads|set_concurrency|m_worker_.*callback",
  "tpool/tpool.h": r"class thread_pool|virtual|set_thread_callbacks|m_worker_.*callback|configure_aio|disable_aio",
  "tpool/task.cc": r"waitable_task::|m_ref_count|m_func|m_cv",
  "storage/innobase/include/read0types.h": r"m_open|append_to|void close|void open",
  "storage/innobase/read/read0read.cc": r"ReadView::|m_open|m_mutex",
  "storage/innobase/include/trx0sys.h": r"register_trx|deregister_trx|freeze|unfreeze|trx_list",
  "storage/innobase/trx/trx0trx.cc": r"TrxFactory|memset\(|was_chosen_as_deadlock_victim|read_view.close|trx_t::free",
  "storage/innobase/include/trx0trx.h": r"was_chosen_as_deadlock_victim|read_view|reference|release_reference",
  "storage/innobase/include/trx0purge.h": r"m_initialized|m_enabled|m_active|skipped_rseg|void create|void close|enabled\(|coordinator",
  "storage/innobase/trx/trx0purge.cc": r"purge_sys_t::|skipped_rseg|m_active|m_enabled|purge_task|wait\(",
  "storage/innobase/srv/srv0srv.cc": r"thread_pool_thread_|srv_thread_pool_|srv_init_purge_tasks|srv_shutdown_purge_tasks|srv_purge_shutdown|purge_thread_count|purge_coordinator_callback|create_timer|\.wait\(",
  "storage/innobase/include/fil0fil.h": r"being_extended|is_corrupted|need_unflushed_spaces|acquire\(|release\(|is_stopping|fil_node_t",
  "storage/innobase/fil/fil0fil.cc": r"being_extended|is_corrupted|need_unflushed_spaces|fil_space_extend_must_retry|fil_space_t::close|fil_space_t::acquire|fil_space_t::release",
  "storage/innobase/fsp/fsp0fsp.cc": r"sysCallback|fsp_system_tablespace_truncate|drop_all_orphaned_tables|scan_system_tables|clear_freed_ranges",
  "storage/innobase/fil/fil0crypt.cc": r"srv_encrypt_rotate|key_get_latest_version|fil_crypt_set_thread_cnt|fil_crypt_threads_cleanup|active_threads|n_fil_crypt_threads_started|cond_wait",
  "sql/encryption.cc": r"encryption_key_get_latest_version_func|no_key",
  "storage/innobase/include/log0recv.h": r"being_processed|page_recv_t|skip_read|last_offset|recovery_on",
  "storage/innobase/log/log0recv.cc": r"being_processed|recovery_on|recv_sys_t::(?:erase|garbage_collect|wait_for_pool|apply|debug_free|clear)|fake_read_complete|free_corrupted_page",
  "storage/innobase/srv/srv0start.cc": r"innodb_shutdown|srv_init_abort_low|debug_free|os_aio_free|recv_sys.apply|recv_sys.close|buf_pool.close|srv_shutdown_threads|fil_crypt_threads_cleanup|srv_thread_pool_end",
  "storage/innobase/buf/buf0dump.cc": r"buf_load_abort_flag|buf_load_abort|buf_load_dump_end|buf_dump_load_task",
  "storage/innobase/lock/lock0lock.cc": r"to_be_checked|was_chosen_as_deadlock_victim|deadlock_check",
  "storage/innobase/include/btr0sea.h": r"hash_analysis|n_hash_potential|last_hash_succ|enabled|disable",
  "storage/innobase/btr/btr0sea.cc": r"hash_analysis|n_hash_potential|last_hash_succ|n_hash_helps|disable_and_lock|btr_sea::enable",
  "storage/innobase/include/dict0mem.h": r"clone\(|hash_analysis|n_hash_potential|last_hash_succ",
  "storage/innobase/dict/dict0mem.cc": r"dict_index_t::clone|\*index = \*this|dict_mem_index_create|dict_mem_index_free",
  "storage/innobase/dict/dict0dict.cc": r"dict_index_remove_from_cache|dict_mem_index_free",
  "storage/innobase/include/buf0buf.h": r"reserved|n_hash_helps|try_LRU_scan|LRU_warned|buf_tmp_buffer_t|io_buf_t",
  "storage/innobase/buf/buf0buf.cc": r"reserved|n_hash_helps|try_LRU_scan|LRU_warned|io_buf_t::|memset\(|memcpy\(|buf_relocate|withdraw|resize",
  "storage/innobase/buf/buf0flu.cc": r"page_cleaner_idle_flag|buf_page_cleaner_is_active|try_LRU_scan|LRU_warned|done|cond_wait",
  "storage/innobase/buf/buf0lru.cc": r"n_hash_helps|try_LRU_scan|buf_LRU_block_free_non_file_page",
  "storage/innobase/os/os0file.cc": r"~io_slots|fake_io_callback|read_io_callback|write_io_callback|os_aio_free|os_fake_read|m_task.m_func|read_slots.*wait|write_slots.*wait",
  "storage/innobase/include/log0log.h": r"need_checkpoint|check_for_checkpoint",
  "storage/innobase/log/log0log.cc": r"need_checkpoint|logs_empty_and_mark_files_at_shutdown|buf_load_dump_end|buf_page_cleaner_is_active|os_aio_wait|rollback.*wait",
  "storage/innobase/include/srw_lock.h": r"SUX_LOCK_GENERIC|pthread_mutex_wrapper|std::atomic|pthread_rwlock|readers_cond",
  "storage/innobase/sync/srw_lock.cc": r"SUX_LOCK_GENERIC|pthread_mutex_wrapper|pthread_cond|atomic_thread_fence|compare_exchange",
  "sql/table_cache.cc": r"tc_contention_warning_reported|lock_and_check_contention",
  "include/my_pthread.h": r"MY_MUTEX_INIT|PTHREAD_MUTEX_ADAPTIVE",
  "include/mysql/plugin.h": r"resolve|MYSQL_THDVAR_BOOL|THDVAR",
  "storage/innobase/handler/ha_innodb.cc": r"MYSQL_THDVAR_BOOL\(table_locks|innodb_buffer_pool_size_update|innodb_adaptive_hash_index_cells_update|innodb_purge_threads_update|buffer_pool_load_abort|innodb_doublewrite_update|innodb_data_file_write_through_update",
 },
 "wasix": {
  "libc-bottom-half/sources/__wasilibc_poly_real.c": r"thread.spawn|import_module",
  "libc-top-half/musl/src/env/__init_tls.c": r"td->tid|0x3fffffff",
  "libc-top-half/musl/arch/wasm32/atomic_arch.h": r"a_barrier|a_cas",
  "libc-top-half/musl/src/internal/atomic.h": r"a_store|a_barrier|a_swap|a_fetch_add",
  "libc-top-half/musl/src/thread/pthread_create.c": r"__tl_|detach_state|a_store|thread_spawn|ret < 0|free\(map\)|free\(self|__wasi_thread_exit",
  "libc-top-half/musl/src/thread/pthread_join.c": r"detach_state|__tl_sync|free|res|timedwait",
  "libc-top-half/musl/src/thread/pthread_detach.c": r"a_cas|pthread_join",
  "libc-top-half/musl/src/thread/pthread_mutex_lock.c": r"_m_lock|_m_waiters|_m_type|a_cas|timedlock",
  "libc-top-half/musl/src/thread/pthread_mutex_timedlock.c": r"_m_lock|_m_waiters|_m_type|a_cas|timedwait",
  "libc-top-half/musl/src/thread/pthread_mutex_unlock.c": r"_m_lock|_m_waiters|_m_type|a_swap|wake",
  "libc-top-half/musl/src/thread/pthread_cond_timedwait.c": r"WAITING|SIGNALED|LEAVING|barrier|ref|relock|unlock|a_cas|timedwait",
  "libc-top-half/musl/src/thread/pthread_rwlock_wrlock.c": r".",
  "libc-top-half/musl/src/thread/pthread_rwlock_rdlock.c": r".",
  "libc-top-half/musl/src/thread/pthread_rwlock_unlock.c": r".",
 },
 "go": {
  "src/cmd/compile/internal/ssa/_gen/genericOps.go": r"StaticLECall|StaticCall|argN=memory|Load.*argLength: 2",
  "src/cmd/compile/internal/ssagen/ssa.go": r"callArgs = append\(callArgs, s.mem\(\)\)|OpStaticLECall|s.vars\[memVar\].*OpSelectN",
  "src/cmd/compile/internal/ssa/_gen/ARM64Ops.go": r"atomic|LoweredAtomic|returns <value,memory>|DMB",
 },
 "converter": {
  "internal/codegen/translate.go": r"MemOpt.*|memOptOK :=|MemoryMayTrap = true",
  "internal/codegen/helpers/helpers.go": r"time.NewTimer\(time.Duration\(timeout\)|func threadLaunch|nextTID.Add|func atomicFence",
 },
 "binaryen": {
  "src/wasm-interpreter.h": r"visitAtomicFence|sequentially consistent|seq_cst",
  "src/wasm2js.h": r"visitAtomicFence|sequentially consistent",
  "src/ir/effects.h": r"visitAtomicFence|sequentially consistent",
 },
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in SELECT:
        p.add_argument("--"+key, type=Path, required=key != "runtime", default=ROOT if key == "runtime" else None)
    for key in ("mariadb-archive", "wasix-archive", "output"):
        p.add_argument("--"+key, type=Path, required=key != "runtime", default=ROOT if key == "runtime" else None)
    a = p.parse_args()
    verify = runpy.run_path(str(ROOT / "benchmarks/spikes/v050-access-paths/scan.py"))["verify_archive"]
    pins = {x["name"]:x for x in json.loads((ROOT / "release/inputs.lock.json").read_text())["inputs"]}
    overrides = {}
    for patch in json.loads((ROOT / "guest/input.json").read_text())["patches"]:
        assert sha(ROOT / patch["file"]) == patch["sha256"]
        overrides.update(patch["after_sha256"])
    counts = {"mariadb": verify(a.mariadb_archive, a.mariadb, pins["mariadb"], overrides),
              "wasix": verify(a.wasix_archive, a.wasix, pins["wasix-libc"])}
    # The archive comparison is a portability-patched reference corpus, not a
    # complete prepared guest. Reproduce canonical diagnostic overlays for the
    # selected source files rather than attributing their pristine line numbers
    # to compiled source.
    hooks = runpy.run_path(str(ROOT / "scripts/guest_init_hooks.py"))
    prepared = json.loads((ROOT / "release/generated-go-build.json").read_text())["prepared_source"]["modified_files"]
    overlay = tempfile.TemporaryDirectory(prefix="mariamem-audit-source-")
    overlay_root = Path(overlay.name)
    for relative in hooks["HOOKS"]:
        target = overlay_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.mariadb / relative, target)
    hooks["instrument"](overlay_root)
    sources, anchors, overlay_matches = {}, [], {}
    for kind, files in SELECT.items():
        source_root = getattr(a, kind)
        for relative, pattern in files.items():
            path = source_root / relative
            if kind == "mariadb" and relative in hooks["HOOKS"]:
                path = overlay_root / relative
            if kind == "mariadb" and relative in prepared:
                assert sha(path) == prepared[relative], f"prepared selected source mismatch: {relative}"
                overlay_matches[relative] = sha(path)
            sources[kind+":"+relative] = sha(path)
            lines = path.read_text().splitlines()
            hits = [i for i,s in enumerate(lines) if re.search(pattern,s)]
            assert hits, f"no anchor: {kind}:{relative}"
            for n in hits:
                anchors.append({"source":kind, "file":relative, "line":n+1, "text":lines[n], "context":lines[max(0,n-2):n+3]})
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / "source-anchors.json").write_text(json.dumps(anchors,indent=2)+"\n")
    (a.output / "source-verification.json").write_text(json.dumps({"verified_source_files":counts, "corpus_stage":"archive plus ordered portability/12.3.3 patches; selected diagnostic-overlay sources separately reconstructed and checked against canonical prepared-source manifest", "selected_prepared_source_matches":overlay_matches, "selected_files_sha256":sources, "anchors":len(anchors), "limit":"Reference extraction supplements manual source tracing; lexical matches alone do not establish alias/ownership completeness."},indent=2)+"\n")
    overlay.cleanup()
    print(f"PASS: {counts}; {len(sources)} selected files, {len(anchors)} anchors")


if __name__ == "__main__":
    main()
