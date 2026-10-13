#!/usr/bin/env python3
"""Create a disposable generated-code candidate from the pinned v0.5.0 source.

The product candidate, if any, must be rebuilt from guest/experimental.patch
and canonical generation. This temporary delta only tests the wakeup hypothesis.
"""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
import sys


root = Path(__file__).resolve().parents[3]
source = root.parent / "temp" / "buf0flu-12.3.3.cc"
expected = "593c16448b8775055e5aa3d48b36a21dd5152bbfbac675c0f9713b0c0183a620"
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise SystemExit("pinned MariaDB source file differs")

old = """      if (buf_pool.page_cleaner_idle() &&
          (!UT_LIST_GET_LEN(buf_pool.flush_list) ||
           srv_max_dirty_pages_pct_lwm == 0.0))
      {
        buf_pool.LRU_warned_clear();
        /* We are idle; wait for buf_pool.page_cleaner_wakeup() */
        my_cond_wait(&buf_pool.do_flush_list,
                     &buf_pool.flush_list_mutex.m_mutex);
      }
      else
        my_cond_timedwait(&buf_pool.do_flush_list,
                          &buf_pool.flush_list_mutex.m_mutex, &abstime);
"""
new = """      /* A checkpoint target can arrive after the pre-lock read. Do not
      sleep on a signal already delivered while acquiring this mutex. */
      if (buf_flush_sync_lsn.load() == 0)
      {
        if (buf_pool.page_cleaner_idle() &&
            (!UT_LIST_GET_LEN(buf_pool.flush_list) ||
             srv_max_dirty_pages_pct_lwm == 0.0))
        {
          buf_pool.LRU_warned_clear();
          /* We are idle; wait for buf_pool.page_cleaner_wakeup() */
          my_cond_wait(&buf_pool.do_flush_list,
                       &buf_pool.flush_list_mutex.m_mutex);
        }
        else
          my_cond_timedwait(&buf_pool.do_flush_list,
                            &buf_pool.flush_list_mutex.m_mutex, &abstime);
      }
"""
original = source.read_text()
if original.count(old) != 1:
    raise SystemExit(f"MariaDB source context changed: {original.count(old)} matches")
patched = original.replace(old, new)
target = "storage/innobase/buf/buf0flu.cc"
diff = difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
                            fromfile="a/" + target, tofile="b/" + target)
(root / "guest" / "experimental.patch").write_text("".join(diff))

if sys.argv[1:] == ["--patch-only"]:
    print("wrote source experiment patch")
    raise SystemExit(0)
if len(sys.argv) != 2:
    raise SystemExit("usage: make_candidate.py <disposable-release-source-root>")
candidate = Path(sys.argv[1]) / "internal/generatedgo/code/p2/p2_pure.go"
text = candidate.read_text()
anchor = """L15:
	;
	v96 = Fn93(m, int32(15209536))
	mBase = m.M
	v99 = base.AtomicLoad32_8u(m, int32(15209756), int32(0))
"""
replacement = """L15:
	;
	v96 = Fn93(m, int32(15209536))
	mBase = m.M
	// Experiment-only equivalent of the source-level post-lock target recheck.
	if atomic.LoadUint64((*uint64)(unsafe.Add(mBase, base.AtomicEA(m, int32(24088376), int32(0), 8)))) != 0 {
		goto L18
	}
	v99 = base.AtomicLoad32_8u(m, int32(15209756), int32(0))
"""
if text.count(anchor) != 1:
    raise SystemExit(f"generated candidate context changed: {text.count(anchor)} matches")
candidate.write_text(text.replace(anchor, replacement))
print("wrote source experiment patch and disposable generated candidate")
