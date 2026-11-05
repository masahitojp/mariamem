#!/usr/bin/env python3
"""Enable native input only; keep all embedded THD/Protocol layouts intact."""
import difflib
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
patch = []
p = root/'sql/sql_prepare.cc'
before = p.read_text()
assert hashlib.sha256(p.read_bytes()).hexdigest() == '2e6d7bebe2d332b3b95690d61c903ecd749b94a04a04820ebd9bc5d8a4957ed3'
lines = before.splitlines(keepends=True)
selected = {205,492,572,585,600,615,629,643,661,865,4165,4176,4606,4798,4890}
for index in selected:
    assert lines[index-1] == '#ifndef EMBEDDED_LIBRARY\n', index
    lines[index-1] = '#if !defined(EMBEDDED_LIBRARY) || defined(ISSUE65_NATIVE_INPUT)\n'
after = ''.join(lines)
after = after.replace('#include <mysql_com.h>\n/* Constants', '#include <mysql_com.h>\n#endif\n#if !defined(EMBEDDED_LIBRARY) || defined(ISSUE65_NATIVE_INPUT)\n/* Constants')
after = after.replace('    uchar *null_array= packet;\n', '''#ifdef ISSUE65_NATIVE_INPUT
    if (thd->client_params != NULL) abort();
    extern unsigned long issue65_decode_count;
    ++issue65_decode_count;
#endif
    uchar *null_array= packet;
''')
after += '\n#ifdef ISSUE65_NATIVE_INPUT\nunsigned long issue65_decode_count= 0;\n#endif\n'
p.write_text(after)
patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/sql/sql_prepare.cc',tofile='b/sql/sql_prepare.cc'))
p = root/'libmysqld/lib_sql.cc'; before = p.read_text(); after = before
assert hashlib.sha256(p.read_bytes()).hexdigest() == '5de14e2760c775701fe7dff7a9cbf4d47266990081f0abf94e88942a943d377e'
start = after.index('  if (stmt->param_count && !stmt->bind_param_done)', after.index('static int emb_stmt_execute'))
end = after.index('  stmt->affected_rows=', start)
after = after[:start] + '''#ifdef ISSUE65_NATIVE_INPUT
  extern const uchar *issue65_packet;
  extern ulong issue65_packet_length;
  thd= (THD*)stmt->mysql->thd;
  if (thd->client_params != NULL || issue65_packet == NULL) abort();
  res= MY_TEST(emb_advanced_command(stmt->mysql, COM_STMT_EXECUTE, 0, 0,
                       issue65_packet, issue65_packet_length, 1, stmt) ||
               emb_read_query_result(stmt->mysql));
  if (thd->client_params != NULL) abort();
#else
''' + after[start:end] + '#endif\n' + after[end:]
after += '''
#ifdef ISSUE65_NATIVE_INPUT
// Single-threaded spike entry only. Bytes include the 9-byte EXECUTE header,
// excluding the command byte and NET frame; no MYSQL_BIND parameters are used.
const uchar *issue65_packet= NULL;
ulong issue65_packet_length= 0;
extern unsigned long issue65_decode_count;
extern "C" unsigned long issue65_decodes() { return issue65_decode_count; }
extern "C" int issue65_raw_execute(MYSQL_STMT *stmt, const uchar *p, ulong n)
{
  if (issue65_packet != NULL) abort();
  issue65_packet= p;
  issue65_packet_length= n;
  int result= mysql_stmt_execute(stmt);
  issue65_packet= NULL;
  issue65_packet_length= 0;
  return result;
}
#endif
'''
p.write_text(after)
patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/libmysqld/lib_sql.cc',tofile='b/libmysqld/lib_sql.cc'))
Path(sys.argv[2]).write_text(''.join(patch))
