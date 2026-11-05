#!/usr/bin/env python3
"""Pinned uncompressed NET reader over memory Vio; no complete engine/ABI claim."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

SEND = Path(__file__).resolve().parents[1] / 'issue65-vio-smoke/run.py'
block = runpy.run_path(str(SEND))['block']
PINS = {
    'sql/net_serv.cc': '7d7b8b8a8de1834099f350912ed9255a1f376565da407e8dc461f97c72f12c93',
    'include/violite.h': '0be1b5c9a8fb6bed71d9a504c7eef69746fa2b388adcd8b68a3642608757f1d4',
    'include/mysql_com.h': '75f5644c62eb9f20882b1730dc6525e45c4b1e58f3c4f97ff229e1aa7cbc986d',
}
FUNCTIONS = [
    'my_bool net_realloc(NET *net,',
    'static handle_proxy_header_result handle_proxy_header(NET *net)',
    'static ulong my_real_read(NET *net,',
    'ulong\nmy_net_read_packet_reallen(NET *net,',
    'ulong\nmy_net_read_packet(NET *net,',
    'ulong my_net_read(NET *net)',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    texts = {}
    for name, sha in PINS.items():
        data = (args.source/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('wrong pinned source: ' + name)
        texts[name] = data.decode()
    tree = ast.parse(SEND.read_text())
    support = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'support' for t in n.targets))
    support += r'''
#include <cstdlib>
#include <string>
using uint32=uint32_t;
#define DBUG_PRINT(...) ((void)0)
#define DBUG_ASSERT(x) assert(x)
#define EXTRA_DEBUG_ASSERT(...) ((void)0)
#define MYSQL_NET_READ_START(...) ((void)0)
#define MYSQL_NET_READ_DONE(...) ((void)0)
#define MYSQL_SERVER_my_error(...) ((void)0)
#define thd_net_is_killed(...) 0
#define vio_read(v,p,n) ((v)->read)((v),(p),(n))
#define vio_was_timeout(v) ((v)->was_timeout)(v)
#define COMP_HEADER_SIZE 3
#define IO_SIZE 4096
#define MY_WME 1
#define MY_THREAD_SPECIFIC 2
#define ER_NET_PACKET_TOO_LARGE 1153
#define ER_OUT_OF_RESOURCES 1041
#define ER_NET_READ_ERROR 1158
#define ER_NET_READ_INTERRUPTED 1159
#define ER_CONNECTION_KILLED 1927
#define packet_error (~0UL)
#define MY_MAX(a,b) ((a)>(b)?(a):(b))
#define my_realloc(k,p,n,f) std::realloc((p),(n))
#define uint3korr(p) (uint32((p)[0]) | (uint32((p)[1])<<8) | (uint32((p)[2])<<16))
'''
    v, m, n = texts['include/violite.h'], texts['include/mysql_com.h'], texts['sql/net_serv.cc']
    types = [block(v, 'enum enum_vio_type'), block(v, 'enum enum_vio_state'),
             block(v, 'enum enum_vio_io_event'), 'typedef struct st_vio Vio;',
             block(v, 'struct st_vio\n'), block(m, 'typedef struct st_net {')+' NET;']
    declarations = r'''
struct st_net_server {
 void *m_user_data;
 void (*m_before_header)(NET*,void*,size_t);
 void (*m_after_header)(NET*,void*,size_t,my_bool);
};
typedef enum { RETRY, ABORT, IGNORE } handle_proxy_header_result;
ulong my_net_read_packet_reallen(NET*,my_bool,ulong*);
ulong my_net_read_packet(NET*,my_bool);
'''
    test = r'''
struct Channel { Vio vio{}; std::vector<uchar> bytes; size_t pos=0,chunk=2,reads=0; };
static size_t get(Vio *v,uchar *p,size_t n) {
 auto *c=reinterpret_cast<Channel*>(v);++c->reads;
 n=std::min({n,c->chunk,c->bytes.size()-c->pos});
 if(n) {std::memcpy(p,c->bytes.data()+c->pos,n);} c->pos+=n;return n;
}
static my_bool no(Vio*) {return false;}
struct Fixture {
 Channel c;NET net{};
 explicit Fixture(size_t chunk=2,ulong limit=32UL*1024*1024) {
  c.chunk=chunk;c.vio.read=get;c.vio.should_retry=no;c.vio.was_timeout=no;c.vio.state=VIO_STATE_ACTIVE;
  net.vio=&c.vio;net.max_packet=4096;net.max_packet_size=limit;
  net.buff=static_cast<uchar*>(std::malloc(net.max_packet+8));assert(net.buff);
  net.buff_end=net.buff+net.max_packet;net.read_pos=net.write_pos=net.buff;
 }
 ~Fixture(){std::free(net.buff);}
 void header(size_t n,uchar seq){assert(n<=0xffffff);c.bytes.push_back(uchar(n));c.bytes.push_back(uchar(n>>8));c.bytes.push_back(uchar(n>>16));c.bytes.push_back(seq);}
 void frame(const std::vector<uchar>& b,uchar seq=0){header(b.size(),seq);c.bytes.insert(c.bytes.end(),b.begin(),b.end());}
 void fill(size_t n,uchar val,uchar seq){header(n,seq);c.bytes.insert(c.bytes.end(),n,val);}
 ulong read(){return my_net_read(&net);}
 void valid(const std::vector<uchar>& b){assert(read()==b.size());assert(std::equal(b.begin(),b.end(),net.read_pos));assert(net.read_pos[b.size()]==0);assert(net.reading_or_writing==0);}
 void eof(){assert(read()==packet_error);assert(net.error==2);assert(net.last_errno==ER_NET_READ_ERROR);assert(net.reading_or_writing==0);}
};
static void ok(const char *name){std::printf("PASS:%s\n",name);}
int main(){
 const std::vector<uchar> payload={3,'S','E','L','E','C','T',' ','1'};
 for(size_t chunk: {size_t(1),size_t(2),size_t(5)}){Fixture f(chunk);f.frame(payload);f.valid(payload);assert(f.c.pos==13);assert(f.c.reads>1);}
 ok("fragmented_header_and_payload_chunks_1_2_5");
 {Fixture f(8192);f.frame({1,2,3},0);f.frame({4,0,5},1);f.valid({1,2,3});f.valid({4,0,5});assert(f.net.pkt_nr==2);assert(f.c.pos==14);}ok("two_frames_keep_sequence");
 {Fixture f;f.frame(payload,2);assert(f.read()==packet_error);assert(f.net.pkt_nr_can_be_reset==0);assert(f.c.pos==4);assert(f.net.reading_or_writing==0);}ok("wrong_sequence_rejected");
 {Fixture f;f.net.pkt_nr=255;f.frame({7},255);f.frame({8},0);f.valid({7});f.valid({8});assert(f.net.pkt_nr==257);}ok("sequence_wrap_255_to_0");
 {Fixture f;f.net.pkt_nr=1;f.frame({1},0);assert(f.read()==packet_error);}ok("previous_sequence_non_error_rejected");
 {Fixture f;f.net.pkt_nr=1;f.frame({255,1},0);f.valid({255,1});}ok("embedded_client_previous_sequence_ERR_exception_observed");
 {Fixture f;f.frame({},0);f.valid({});}ok("empty_packet");
 {Fixture f;f.c.bytes={9,0};f.eof();}ok("EOF_mid_header");
 {Fixture f;f.header(9,0);f.c.bytes.push_back(3);f.eof();}ok("EOF_mid_payload");
 {Fixture f(8191);f.fill(65535,0x5a,0);assert(f.read()==65535);assert(f.net.max_packet==65536);assert(f.net.read_pos[65534]==0x5a);}ok("upstream_buffer_reallocation");
 {Fixture f(8191,65536);f.fill(65535,0x5a,0);assert(f.read()==65535);f.fill(65536,0x6b,1);assert(f.read()==packet_error);assert(f.net.error==1);assert(f.net.last_errno==ER_NET_PACKET_TOO_LARGE);}ok("configured_limit_after_prior_growth");
 {Fixture f(8191,65536);f.header(65537,0);assert(f.read()==packet_error);assert(f.net.last_errno==ER_NET_PACKET_TOO_LARGE);assert(f.c.pos==4);}ok("over_limit_rejected_after_header");
 {Fixture f(8191);f.fill(0xffffff,0x5a,0);f.fill(7,0x6b,1);assert(f.read()==0xffffffUL+7);assert(f.net.where_b==0);assert(f.net.pkt_nr==2);assert(std::all_of(f.net.read_pos,f.net.read_pos+0xffffff,[](uchar x){return x==0x5a;}));assert(std::all_of(f.net.read_pos+0xffffff,f.net.read_pos+0xffffff+7,[](uchar x){return x==0x6b;}));assert(f.net.read_pos[0xffffff+7]==0);}ok("ffffff_plus_tail_reassembled");
 {Fixture f(8191);f.fill(0xffffff,0x5a,0);f.header(0,1);assert(f.read()==0xffffffUL);assert(f.net.where_b==0);assert(f.net.pkt_nr==2);assert(std::all_of(f.net.read_pos,f.net.read_pos+0xffffff,[](uchar x){return x==0x5a;}));assert(f.net.read_pos[0xffffff]==0);}ok("exact_ffffff_requires_empty_terminator");
 {Fixture f(8191);f.fill(0xffffff,0x5a,0);f.eof();assert(f.net.where_b==0);}ok("missing_continuation_terminator_EOF");
}
'''
    args.output.mkdir(parents=True,exist_ok=False)
    source=args.output/'read.cc'
    bodies={f:block(n,f) for f in FUNCTIONS}
    source.write_text(n[:n.index('*/')+2]+'\n'+support+'\n'+'\n'.join(types)+declarations+'\n'+'\n'.join(bodies.values())+test)
    binary=args.output/'read'
    flags=['-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer']
    compiled=subprocess.run(['g++',*flags,str(source),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    (args.output/'compile.txt').write_text(compiled.stdout+compiled.stderr)
    record={'upstream_source_commit':'83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e','inputs_sha256':PINS,'functions_sha256':{f:hashlib.sha256(s.encode()).hexdigest() for f,s in bodies.items()},'generated_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'support_harness_sha256':hashlib.sha256(SEND.read_bytes()).hexdigest(),'profile':{'EMBEDDED_LIBRARY':True,'MYSQL_SERVER':False,'HAVE_COMPRESS':False,'pkt_nr_can_be_reset':False,'retry_count':0,'extension':None},'compile_returncode':compiled.returncode,'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],'flags':flags,'scope':'isolated native NET read/framing, not complete headers/ABI, THD, SQL or prepared integration'}
    code=compiled.returncode
    if not code:
        ran=subprocess.run([str(binary)],capture_output=True,text=True,timeout=20)
        (args.output/'run.txt').write_text(ran.stdout+ran.stderr);code=ran.returncode
        record.update(run_returncode=code,cases=[s[5:] for s in ran.stdout.splitlines() if s.startswith('PASS:')],binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
        print(ran.stdout+ran.stderr,flush=True)
    else:print(compiled.stderr,flush=True)
    (args.output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    raise SystemExit(code)

if __name__=='__main__':main()
