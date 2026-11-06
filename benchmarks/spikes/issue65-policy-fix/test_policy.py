"""Check the small native policy against the declared profile and seam ordering."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
PATCH=(ROOT/'guest/experimental.patch').read_text()


def section(name):
    found=re.search(r'(?ms)^--- a/'+re.escape(name)+r'\n\+\+\+ b/'+re.escape(name)+r'\n(.*?)(?=^--- a/|\Z)',PATCH)
    if not found:raise ValueError('missing patch: '+name)
    return found[1]


def added_file(name):
    return ''.join(line[1:]+'\n' for line in section(name).splitlines() if line.startswith('+'))


class NativePolicyTests(unittest.TestCase):
    def test_decoded_profile_and_numeric_boundaries(self):
        commands=json.loads((ROOT/'docs/reviews/v06x-fixture-acceptance.json').read_text())['wire']['supported_commands']
        compiler=shutil.which('c++')
        self.assertIsNotNone(compiler)
        program='''#include "mariamem_wire_policy.h"
#include <assert.h>
int main(){
unsigned accepted[]={COMMANDS};
for(unsigned c=0;c<256;c++){bool expected=false;for(unsigned v:accepted)if(c==v)expected=true;assert(mariamem_wire_command_allowed(c)==expected);}
for(uint64_t f=0;f<65536;f++)assert(mariamem_wire_handshake_allowed(f)==((f&512)!=0&&(f&2048)==0));
assert(mariamem_wire_handshake_allowed((1ULL<<63)|512));
size_t good[]={0,1,0xfffffd,0xfffffe};for(size_t n:good)assert(mariamem_wire_output_allowed(n));
size_t bad[]={0xffffff,0x1000000,size_t(-1)};for(size_t n:bad)assert(!mariamem_wire_output_allowed(n));
}
'''.replace('COMMANDS',','.join(map(str,commands)))
        with tempfile.TemporaryDirectory(prefix='issue65-policy-') as tmp:
            p=Path(tmp);(p/'mariamem_wire_policy.h').write_text(added_file('sql/mariamem_wire_policy.h'))
            (p/'check.cc').write_text(program)
            subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror','-I',str(p),str(p/'check.cc'),'-o',str(p/'check')],check=True)
            subprocess.run([str(p/'check')],check=True)

    def test_native_guards_before_the_authoritative_operations(self):
        acl=section('sql/sql_acl.cc');net=section('sql/net_serv.cc');sql=section('sql/sql_parse.cc')
        self.assertLess(acl.index('mariamem_wire_handshake_allowed(client_capabilities)'),acl.index('thd->client_capabilities&= client_capabilities'))
        self.assertLess(net.index('mariamem_wire_output_allowed(len)'),net.index('MYSQL_NET_WRITE_START(len)'))
        self.assertLess(sql.index('mariamem_wire_command_allowed(command)'),sql.index('switch (command)'))
        self.assertIn('goto dispatch_end;',sql)
        self.assertIn('net->thd && static_cast<THD*>(net->thd)->mariamem_native_wire',net)
        self.assertIn('thd->mariamem_native_wire &&',sql)

    def test_auth_error_delivery_precedes_retirement(self):
        body=added_file('libmysqld/lib_sql.cc')
        start=body.index('if(!result && acl_authenticate(thd,0)) {')
        end=body.index('else if(!result)',start)
        rejection=body[start:end]
        self.assertLess(rejection.index('end_statement()'),rejection.index('net_flush('))
        self.assertLess(rejection.index('net_flush('),rejection.index('CONNECTION_COMPLETE'))
        self.assertLess(start,body.index('UNREGISTER_THD,thd',end))

if __name__=='__main__':unittest.main()
