#!/usr/bin/env python3
"""Build a mandatory-flag, coherent embedded/native-wire experiment patch."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import sys
import tarfile

root=Path(sys.argv[1]); out=Path(sys.argv[2]); originals={}; changes={}
archive=root.parent/'mariadb-12.3.3-source.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845'
tar=tarfile.open(archive); members={m.name.split('/',1)[1]:m for m in tar.getmembers() if '/' in m.name}
def read(name):
    text=tar.extractfile(members[name]).read().decode(); originals.setdefault(name,text); return text
def save(name,text): changes[name]=text
def region(s,marker,start=0):
    a=s.index(marker,start); lineend=s.index('\n',a)+1; depth=1; mid=None
    for m in re.finditer(r'(?m)^#\s*(if\w*|else|endif)\b[^\n]*\n?',s[lineend:]):
        kind=m.group(1); x=lineend+m.start(); y=lineend+m.end()
        if kind.startswith('if'): depth+=1
        elif kind=='endif':
            depth-=1
            if depth==0:return a,y,s[lineend:mid[0] if mid else x],s[mid[1]:x] if mid else ''
        elif kind=='else' and depth==1: mid=(x,y)
    raise ValueError(marker)
def function(s,name,start=0):
    m=re.search(r'(?m)^(?:static )?(?:bool|void|int)\s*\n?'+re.escape(name)+r'\s*\(',s[start:])
    if not m:raise ValueError('function '+name)
    a=start+m.start(); b=s.index('{',start+m.end()); depth=1; i=b+1; state='code'
    while depth:
        c=s[i]; n=s[i:i+2]
        if state=='code':
            if n=='//':state='line';i+=1
            elif n=='/*':state='comment';i+=1
            elif c in '\"\'':state=c
            elif c=='{':depth+=1
            elif c=='}':depth-=1
        elif state=='line':
            if c=='\n':state='code'
        elif state=='comment':
            if n=='*/':state='code';i+=1
        else:
            if c=='\\':i+=1
            elif c==state:state='code'
        i+=1
    return a,b,i

def runtime_guards(body,condition):
    while '#ifndef EMBEDDED_LIBRARY' in body:
        a,b,native,embedded=region(body,'#ifndef EMBEDDED_LIBRARY')
        body=body[:a]+'if ('+condition+') {\n'+native+'}\n'+('else {\n'+embedded+'}\n' if embedded else '')+body[b:]
    return body

# Constructor mode precedes Protocol members; all existing callers default embedded.
s=read('sql/sql_class.h').replace('  NET\t  net;', '  const bool mariamem_native_wire;\n  NET\t  net;')
s=s.replace('THD(my_thread_id id, bool is_wsrep_applier= false);','THD(my_thread_id id, bool is_wsrep_applier= false, bool native_wire= false);')
assert 'const bool mariamem_native_wire' in s;save('sql/sql_class.h',s)
s=read('sql/sql_class.cc').replace('THD::THD(my_thread_id id, bool is_wsrep_applier)','THD::THD(my_thread_id id, bool is_wsrep_applier, bool native_wire)').replace('   protocol_text(this),','   mariamem_native_wire(native_wire),\n   protocol_text(this),');save('sql/sql_class.cc',s)

# Compile native response bodies under new helper names; embedded public entries dispatch.
p=read('sql/protocol.cc');lib=read('libmysqld/lib_sql.cc');header=read('sql/protocol.h')
lib=lib.replace('            bool)\n{','            bool is_eof)\n{',1)
for name in ['net_store_data','net_store_data_cs']:
    a,b,n,e=region(p,'#ifndef EMBEDDED_LIBRARY',p.index('bool Protocol::'+name+'(')-30)
    p=p[:a]+n+p[b:]
helpers={
 'Protocol::net_store_data':'from, length',
 'Protocol::net_store_data_cs':'from, length, from_cs, to_cs',
 'Protocol::net_send_ok':'thd, server_status, statement_warn_count, affected_rows, id, message, is_eof',
 'Protocol::net_send_eof':'thd, server_status, statement_warn_count',
 'Protocol::net_send_error_packet':'thd, sql_errno, err, sqlstate',
 'Protocol_text::store_field_metadata':'thd, server_field, charset_for_protocol, pos',
 'Protocol::send_result_set_metadata':'list, flags',
 'Protocol::send_list_fields':'list, table_list',
 'Protocol::write':'',
 'Protocol_text::prepare_for_resend':'',
 'Protocol_text::store_null':'',
}
decls={}
for name,args in helpers.items():
    cls,method=name.split('::');a,b,end=function(p,name);signature=p[a:b].strip();wire=cls+'::wire_'+method
    decl=signature.replace(name,'wire_'+method)+';';decls.setdefault(cls,[]).append(decl)
    p=p[:a]+p[a:end].replace(name,wire,1)+p[end:]
    a,b,end=function(lib,name);ret='return '+('' if signature.startswith('void') else '')
    branch='\n  if (this->thd->mariamem_native_wire) '+ret+'wire_'+method+'('+args+');\n'
    lib=lib[:b+1]+branch+lib[b+1:]
for cls,entries in decls.items():
    token='class '+cls+(' final' if cls=='Protocol_binary' else '')+(' :public Protocol' if cls!='Protocol' else '')+'\n{'
    assert token in header,token
    header=header.replace(token,token+'\npublic:\n'+'\n'.join(entries)+'\nprivate:\n',1)
p=p.replace('#ifndef EMBEDDED_LIBRARY','#if !defined(EMBEDDED_LIBRARY) || defined(MARIAMEM_NATIVE_WIRE)')
p=p.replace('    thd->session_tracker.store(thd, &store);', '#ifdef EMBEDDED_LIBRARY\n    abort(); // SESSION_TRACK is outside this explicitly advertised profile.\n#else\n    thd->session_tracker.store(thd, &store);\n#endif')
a,b,end=function(p,'Protocol::flush');p=p[:b+1]+'\n  if (!thd->mariamem_native_wire) return false;\n'+p[b+1:]
p+='''\nbool Protocol_binary::net_store_data(const uchar *p, size_t n)
{ return wire_net_store_data(p,n); }
bool Protocol_binary::net_store_data_cs(const uchar *p, size_t n, CHARSET_INFO *f, CHARSET_INFO *t)
{ return wire_net_store_data_cs(p,n,f,t); }
'''
a,b,end=function(lib,'Protocol_binary::write');lib=lib[:b+1]+'\n  if (thd->mariamem_native_wire) return wire_write();\n'+lib[b+1:]
# Preserve the existing embedded helper, with an explicit constructor mode for wire owners.
lib=lib.replace('void *create_embedded_thd(ulong client_flag)\n{\n  THD * thd= new THD(next_thread_id());','static THD *create_spike_thd(ulong client_flag, bool wire)\n{\n  THD * thd= new THD(next_thread_id(), false, wire);')
where=lib.index('\n\nTHD *embedded_get_current_thd()');lib=lib[:where]+'\n\nextern "C" void *create_embedded_thd(ulong flags) { return create_spike_thd(flags,false); }\n'+lib[where:]
lib+='\n#include "mariamem_wire_probe.inc"\n'
save('sql/protocol.cc',p);save('sql/protocol.h',header);save('libmysqld/lib_sql.cc',lib)

# Server NET semantics, while every class/header remains embedded.
s=read('sql/net_serv.cc').replace('#ifdef EMBEDDED_LIBRARY\n#undef MYSQL_SERVER','#if defined(EMBEDDED_LIBRARY) && !defined(MARIAMEM_NATIVE_WIRE)\n#undef MYSQL_SERVER');save('sql/net_serv.cc',s)

# Per-THD prepared representation: native routines and embedded C API both survive.
s=read('sql/sql_prepare.cc')
s=s.replace('#include <mysql_com.h>\n/* Constants','#include <mysql_com.h>\n#endif\n#if 1 /* native type constant is also needed in hybrid mode */\n/* Constants')
a,b,n,e=region(s,'#ifndef EMBEDDED_LIBRARY',s.index('  my_bool read_types;'));s=s[:a]+n+e+s[b:]
a,b,n,e=region(s,'#ifndef EMBEDDED_LIBRARY',s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('static bool send_prep_stmt')))
n=n.replace('send_prep_stmt(','send_prep_stmt_wire(',1)
_,body,_=function(e,'send_prep_stmt');e=e[:body+1]+'\n  if (stmt->thd->mariamem_native_wire) return send_prep_stmt_wire(stmt, columns);\n'+e[body+1:]
s=s[:a]+n+e+s[b:]
a,b,n,e=region(s,'#ifndef EMBEDDED_LIBRARY',s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('static ulong get_param_length')))
n=n.replace('get_param_length(','get_wire_param_length(',1)
s=s[:a]+n+'\n#define get_param_length(p,n) (current_thd->mariamem_native_wire ? get_wire_param_length(p,n) : (n))\n'+s[b:]
for name in ['tiny','short','int32','int64','float','double']:
    a,b,end=function(s,'Item_param::set_param_'+name);s=s[:a]+runtime_guards(s[a:end],'current_thd->mariamem_native_wire')+s[end:]
a,b,n,e=region(s,'#ifndef EMBEDDED_LIBRARY',s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('void Item_param::set_param_time')))
item=read('sql/item.h')
for name in ['time','datetime','date']:
    method='set_param_'+name
    e=e.replace('Item_param::'+method+'(','Item_param::'+method+'_embedded(')
    aa,bb,ee=function(n,'Item_param::'+method);n=n[:bb+1]+'\n  if (!current_thd->mariamem_native_wire) return '+method+'_embedded(pos,len);\n'+n[bb+1:]
    token='  void '+method+'(uchar **pos, ulong len);';assert token in item
    item=item.replace(token,token+'\n  void '+method+'_embedded(uchar **pos, ulong len);')
s=s[:a]+n+e+s[b:];save('sql/item.h',item)
a,b,n,e=region(s,'#ifndef EMBEDDED_LIBRARY',s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('static bool insert_params_with_log')))
s=s[:a]+n+e+s[b:]
for name in ['Prepared_statement::setup_set_params','Prepared_statement::set_parameters','mysql_stmt_get_longdata']:
    a,b,end=function(s,name)
    text=s[a:end]
    if name=='mysql_stmt_get_longdata':
        text=text.replace('#ifndef EMBEDDED_LIBRARY\n  char *packet_end= packet + packet_length;\n#endif','  char *packet_end= packet + packet_length;')
    text=runtime_guards(text,'thd->mariamem_native_wire')
    s=s[:a]+text+s[end:]
# Bulk remains out of the probe's command set; keep a safe embedded rejection.
s=s.replace('#ifndef EMBEDDED_LIBRARY\n    if ((*set_bulk_params)(this, &packet, packet_end, reset))\n#else\n    // bulk parameters are not supported for embedded, so it will an error\n#endif','    if (!thd->mariamem_native_wire || (*set_bulk_params)(this, &packet, packet_end, reset))')
s=s.replace('#ifndef EMBEDDED_LIBRARY\n  if (read_types &&\n      set_conversion_functions(this, &packet))\n#else\n  // bulk parameters are not supported for embedded, so it will an error\n#endif','  if (!thd->mariamem_native_wire || (read_types && set_conversion_functions(this, &packet)))')
s=s.replace('    uchar *null_array= packet;','    if (thd->client_params != NULL) abort();\n    extern unsigned long mariamem_spike_decodes;\n    ++mariamem_spike_decodes;\n    uchar *null_array= packet;')
s+='\nunsigned long mariamem_spike_decodes= 0;\n';save('sql/sql_prepare.cc',s)

# A distinct memory transport is not an encrypted socket.
s=read('include/violite.h').replace('  VIO_TYPE_SSL\n','  VIO_TYPE_SSL, VIO_TYPE_MEMORY\n').replace('#define LAST_VIO_TYPE VIO_TYPE_SSL','#define LAST_VIO_TYPE VIO_TYPE_MEMORY');save('include/violite.h',s)
s=read('sql-common/client.c').replace('  case VIO_TYPE_TCPIP:\n','  case VIO_TYPE_MEMORY:\n  case VIO_TYPE_TCPIP:\n',1);save('sql-common/client.c',s)
s=read('sql/sql_acl.cc')
marker='static plugin_ref get_auth_plugin(THD *thd, const LEX_CSTRING &name, bool *locked)\n{'
assert marker in s
s=s.replace(marker,marker+'\n  if (thd && thd->mariamem_native_wire) {\n    *locked=true;\n    return my_plugin_lock_by_name(thd, &name, MYSQL_AUTHENTICATION_PLUGIN);\n  }\n',1)
# The upstream initial-handshake decoder is otherwise a zero-return stub.
a=s.index('static ulong parse_client_handshake_packet(');b=s.index('\n}',a)+2
text=runtime_guards(s[a:b],'mpvio->auth_info.thd->mariamem_native_wire')
text=text.replace('  thd->password= passwd_len > 0;','''#ifndef NO_EMBEDDED_ACCESS_CHECKS
  thd->password= passwd_len > 0;''',1)
text=text.replace('  return (ulong)passwd_len;','''  return (ulong)passwd_len;
#else
  return packet_error; // initialized is zero; native skip-grants returned above.
#endif''',1)
s=s[:a]+text+s[b:]
s=s.replace('/* few defines to have less ifdef\'s in the code below */', '''#ifdef NO_EMBEDDED_ACCESS_CHECKS
// Same non-SSL constants as the upstream ACL-only definition.
#define MIN_HANDSHAKE_SIZE 6
#define NORMAL_HANDSHAKE_SIZE 6
#endif
/* few defines to have less ifdef's in the code below */''')
a=s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('static bool check_require_secured_transport'))
s=s[:a]+s[a:].replace('#ifndef EMBEDDED_LIBRARY','#if !defined(EMBEDDED_LIBRARY) || defined(MARIAMEM_NATIVE_WIRE)',1)
needle='  end= strnmov(end, server_version, SERVER_VERSION_LENGTH) + 1;'
s=s.replace(needle,'  if (thd->mariamem_native_wire)\n    thd->client_capabilities= 1ULL|4|8|512|8192|32768|65536|131072|524288|262144;\n\n'+needle,1)
save('sql/sql_acl.cc',s)

# Enable upstream blocking command reader only, not listener/scheduler.
s=read('sql/sql_parse.cc');i=s.rfind('#ifndef EMBEDDED_LIBRARY',0,s.index('static enum enum_server_command fetch_command'));assert i>=0
s=s[:i]+s[i:].replace('#ifndef EMBEDDED_LIBRARY','#if !defined(EMBEDDED_LIBRARY) || defined(MARIAMEM_NATIVE_WIRE)',1);save('sql/sql_parse.cc',s)

# Test-only native session entry contains no replacement protocol encoder.
name='libmysqld/mariamem_wire_probe.inc';originals[name]='';save(name,Path(__file__).with_name('session.inc').read_text())
patch=[]
for name,before in originals.items():
    after=changes[name]
    if not (root/name).exists() or (root/name).read_text()!=after: (root/name).write_text(after)
    if after!=before:patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name if before else '/dev/null',tofile='b/'+name))
out.write_text(''.join(patch))
Path(sys.argv[3]).write_text(json.dumps({n:{'before_sha256':hashlib.sha256(v.encode()).hexdigest(),'after_sha256':hashlib.sha256((root/n).read_bytes()).hexdigest()} for n,v in originals.items()},indent=2)+'\n')
print('Patch files:',len(originals))
