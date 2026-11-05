#!/usr/bin/env python3
"""Isolated upstream NET/Vio send seam, NOT an embedded engine or ABI test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def block(text, start):
    at = text.index(start)
    begin = text.index('{', at)
    depth = 0
    for end in range(begin, len(text)):
        if text[end] == '{': depth += 1
        elif text[end] == '}': depth -= 1
        if not depth:
            end += 1
            if text[end:end+1] == ';': end += 1
            return text[at:end]
    raise ValueError('unterminated source block')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--compiler', default='clang++')
    a = p.parse_args()
    expected = {
        'sql/net_serv.cc': '7d7b8b8a8de1834099f350912ed9255a1f376565da407e8dc461f97c72f12c93',
        'include/violite.h': '0be1b5c9a8fb6bed71d9a504c7eef69746fa2b388adcd8b68a3642608757f1d4',
        'include/mysql_com.h': '75f5644c62eb9f20882b1730dc6525e45c4b1e58f3c4f97ff229e1aa7cbc986d',
    }
    inputs = {}
    for name in ('sql/net_serv.cc','include/violite.h','include/mysql_com.h'):
        b = (a.source/name).read_bytes()
        inputs[name] = hashlib.sha256(b).hexdigest()
        if name in expected and inputs[name] != expected[name]: raise ValueError('wrong pinned source')
    n = (a.source/'sql/net_serv.cc').read_text()
    v = (a.source/'include/violite.h').read_text()
    m = (a.source/'include/mysql_com.h').read_text()
    pieces = [block(v, 'enum enum_vio_type'), block(v, 'enum enum_vio_state'),
              block(v, 'enum enum_vio_io_event'), 'typedef struct st_vio Vio;',
              block(v, 'struct st_vio\n'), block(m, 'typedef struct st_net {') + ' NET;']
    # The upstream typedef closing name follows its brace, unlike a struct.
    funcs = ['my_bool net_flush(NET *net)', 'my_bool my_net_write(NET *net,',
             'static my_bool\nnet_write_buff(NET *net,', 'int\nnet_real_write(NET *net,']
    for f in funcs: pieces.append(block(n, f))
    support = r'''
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#include <sys/socket.h>
#include <sys/types.h>
using uchar=unsigned char; using uint=unsigned int; using ulong=unsigned long;
using my_bool=char; using my_socket=int; using uint16=uint16_t;
struct MYSQL_SOCKET { my_socket fd; void *m_psi; };
#define EMBEDDED_LIBRARY 1
#define DBUG_OFF 1
#define MYSQL_ERRMSG_SIZE 512
#define SQLSTATE_LENGTH 5
#define MAX_PACKET_LENGTH 16777215U
#define NET_HEADER_SIZE 4
#define DBUG_ENTER(...) ((void)0)
#define DBUG_DUMP(...) ((void)0)
#define DBUG_RETURN(x) return (x)
#define MYSQL_NET_WRITE_START(...) ((void)0)
#define MYSQL_NET_WRITE_DONE(...) ((void)0)
#define MYSQL_SERVER_my_error(...) ((void)0)
#define MYF(x) (x)
#define MY_TEST(x) ((x)!=0)
#define likely(x) (x)
#define unlikely(x) (x)
#define EXTRA_DEBUG_fprintf(...) ((void)0)
#define update_statistics(...) ((void)0)
#define ER_NET_ERROR_ON_WRITE 1160
#define ER_NET_WRITE_INTERRUPTED 1161
#define vio_write(v,p,n) ((v)->write)((v),(p),(n))
#define vio_should_retry(v) ((v)->should_retry)(v)
#define int3store(p,x) do { (p)[0]=(uchar)(x); (p)[1]=(uchar)((x)>>8); (p)[2]=(uchar)((x)>>16); } while(0)
'''
    forward = '\nstatic my_bool net_write_buff(NET*,const uchar*,size_t);\nint net_real_write(NET*,const uchar*,size_t);\n'
    test = r'''
struct Channel { Vio vio{}; std::vector<uchar> bytes; size_t pos=0, chunk=2, writes=0; bool fail=false; };
static size_t put(Vio *v,const uchar *p,size_t n) {
 auto *c=reinterpret_cast<Channel*>(v); ++c->writes;
 if(c->fail) return size_t(-1);
 n=std::min(n,c->chunk); c->bytes.insert(c->bytes.end(),p,p+n); return n;
}
static size_t get(Vio *v,uchar *p,size_t n) {
 auto *c=reinterpret_cast<Channel*>(v);
 n=std::min({n,c->chunk,c->bytes.size()-c->pos});
 if(n) { std::memcpy(p,c->bytes.data()+c->pos,n); }
 c->pos+=n; return n;
}
static my_bool retry(Vio*) { return false; }
struct Fixture { Channel c; NET net{}; uchar cache[8]{};
 Fixture() { c.vio.read=get;c.vio.write=put;c.vio.should_retry=retry;c.vio.state=VIO_STATE_ACTIVE;
 net.vio=&c.vio;net.buff=net.write_pos=cache;net.buff_end=cache+sizeof(cache);net.max_packet=sizeof(cache); }
};
int main() {
 const uchar payload[]={3,'S','E','L','E','C','T',' ','1'};
 const std::vector<uchar> expected={9,0,0,0,3,'S','E','L','E','C','T',' ','1'};
 Fixture f; assert(my_net_write(&f.net,payload,sizeof(payload))==0); assert(net_flush(&f.net)==0);
 assert(f.c.bytes==expected);assert(f.net.pkt_nr==1);assert(f.c.writes>1);
 uchar back[13]{};size_t off=0;while(off<sizeof(back)) {size_t n=f.c.vio.read(&f.c.vio,back+off,sizeof(back)-off);assert(n);off+=n;}
 assert(std::equal(expected.begin(),expected.end(),back));assert(f.c.vio.read(&f.c.vio,back,1)==0);
 Fixture empty;assert(my_net_write(&empty.net,payload,0)==0);assert(net_flush(&empty.net)==0);
 assert(empty.c.bytes==std::vector<uchar>({0,0,0,0}));
 Fixture sequence;sequence.net.pkt_nr=7;assert(my_net_write(&sequence.net,payload,1)==0);assert(net_flush(&sequence.net)==0);
 assert(sequence.c.bytes==std::vector<uchar>({1,0,0,7,3}));assert(sequence.net.pkt_nr==8);
 Fixture bad;bad.c.fail=true;assert(my_net_write(&bad.net,payload,1)==0);assert(net_flush(&bad.net)!=0);
 assert(bad.net.error==2);assert(bad.net.last_errno==ER_NET_ERROR_ON_WRITE);assert(bad.net.reading_or_writing==0);
 assert(bad.c.bytes.empty());assert(net_flush(&bad.net)==0); // no cached pending data
 std::puts("PASS: exact frame, partial writes, callback read/EOF, empty frame, sequence, write failure");
}
'''
    a.output.mkdir(parents=True,exist_ok=False)
    source = a.output/'smoke.cc'
    source.write_text(n[:n.index('*/')+2]+'\n'+support+'\n'+'\n'.join(pieces[:6])+forward+'\n'+'\n'.join(pieces[6:])+test)
    binary = a.output/'smoke'
    cmd=[a.compiler,'-std=c++17','-Wall','-Wextra','-Werror','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(source),'-o',str(binary)]
    compiled=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
    (a.output/'compile.txt').write_text(compiled.stdout+compiled.stderr)
    record={'source_commit':'83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e','kind':'isolated-source-extraction-NET-Vio-send-seam','inputs_sha256':inputs,'generated_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'compile_returncode':compiled.returncode,'compiler_version':subprocess.check_output([a.compiler,'--version'],text=True).splitlines()[0],'limitations':['No complete MariaDB build or embedded THD','No native packet reader, handshake, SQL, prepared decoding or result metadata','Only extracted upstream NET/Vio types and four unmodified writer functions','Harness supplies platform typedefs, buffer setup and disabled diagnostic hooks; no ABI proof','Compression, large continuation, retry/timeout/concurrency untested']}
    if not compiled.returncode:
        ran=subprocess.run([str(binary)],text=True,capture_output=True,timeout=10)
        (a.output/'run.txt').write_text(ran.stdout+ran.stderr);record['run_returncode']=ran.returncode;record['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest();print(ran.stdout+ran.stderr,flush=True)
    else:print(compiled.stderr,flush=True)
    (a.output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    raise SystemExit(compiled.returncode or record.get('run_returncode',1))

if __name__=='__main__':main()
