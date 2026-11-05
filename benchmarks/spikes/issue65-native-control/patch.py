#!/usr/bin/env python3
"""Extend the preserved3A patch; emit a complete pristine-to3B delta."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args();spike=Path(__file__).resolve().parent;repo=spike.parents[2]
args.evidence.mkdir(exist_ok=True,parents=True)
subprocess.run([sys.executable,str(repo/'benchmarks/spikes/issue65-native-login/patch.py'),str(args.source),str(args.evidence/'base3A.patch'),str(args.evidence/'base3A-files.json')],check=True)
manifest=json.loads((args.evidence/'base3A-files.json').read_text());files=set(manifest)
p=args.source/'libmysqld/mariamem_wire_probe.inc';p.write_bytes((spike/'session.inc').read_bytes())
p=args.source/'libmysqld/mariamem_control_abi.h';p.write_bytes((spike/'control_abi.h').read_bytes());files.add('libmysqld/mariamem_control_abi.h')
p=args.source/'libmysqld/lib_sql.cc';s=p.read_text().replace('void Protocol_text::remove_last_row()\n{','void Protocol_text::remove_last_row()\n{\n  if (thd->mariamem_native_wire) return Protocol::remove_last_row();',1);p.write_text(s)
p=args.source/'sql/sql_prepare.cc';s=p.read_text().replace('++mariamem_spike_decodes;','__atomic_fetch_add(&mariamem_spike_decodes,1UL,__ATOMIC_RELAXED);');p.write_text(s)
p=args.source/'sql/sql_parse.cc';s=p.read_text().replace('resume:\n  return_value= dispatch_command(command, thd, packet+1,','resume:\n  if (thd->mariamem_native_wire) {\n    extern bool mariamem_spike_dispatch_start(THD*, enum enum_server_command);\n    if (mariamem_spike_dispatch_start(thd,command)) return DISPATCH_COMMAND_CLOSE_CONNECTION;\n  }\n  return_value= dispatch_command(command, thd, packet+1,',1);p.write_text(s)
p=args.source/'sql/net_serv.cc';s=p.read_text().replace('      len= uint3korr(net->buff + net->where_b);','''      len= uint3korr(net->buff + net->where_b);
      if (net->thd && static_cast<THD*>(net->thd)->mariamem_native_wire &&
          (len == 0 || len > 1048577UL))
      {
        net->error= 1;
        net->last_errno= ER_NET_PACKET_TOO_LARGE;
        MYSQL_SERVER_my_error(ER_NET_PACKET_TOO_LARGE, MYF(0));
        len= packet_error;
        goto end;
      }''',1);p.write_text(s)
archive=args.source.parent/'mariadb-12.3.3-source.tar.gz';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845'
patch=[];pins={}
with tarfile.open(archive) as tar:
 members={m.name.split('/',1)[1]:m for m in tar.getmembers() if '/' in m.name}
 for name in sorted(files):
  old=tar.extractfile(members[name]).read() if name in members else b'';new=(args.source/name).read_bytes()
  pins[name]={'before_sha256':hashlib.sha256(old).hexdigest() if old else None,'after_sha256':hashlib.sha256(new).hexdigest()}
  patch.extend(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='a/'+name if old else '/dev/null',tofile='b/'+name))
(repo/'guest/experimental.patch').write_text(''.join(patch))
(args.evidence/'source-files.json').write_text(json.dumps(pins,indent=2)+'\n')
print('Full3B patch paths:',len(pins))
