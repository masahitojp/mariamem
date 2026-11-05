#include <mysql.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <algorithm>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <unistd.h>
#include <signal.h>
#include "routine_bootstrap.inc"
extern "C" int mariamem_spike_session(void*,size_t(*)(void*,unsigned char*,size_t),size_t(*)(void*,const unsigned char*,size_t));
extern "C" unsigned long mariamem_spike_decode_count();
static void need(bool ok,const char *msg){if(!ok){fprintf(stderr,"FAIL:%s\n",msg);std::exit(1);}}
struct Queue{std::mutex mu;std::condition_variable cv;std::deque<unsigned char> data;bool eof=false;size_t peak=0;};
struct Transport{Queue input,output;};
static size_t get(void *ctx,unsigned char *p,size_t n){auto &q=((Transport*)ctx)->input;std::unique_lock<std::mutex> lock(q.mu);q.cv.wait(lock,[&]{return !q.data.empty()||q.eof;});n=std::min({n,q.data.size(),size_t(2)});for(size_t i=0;i<n;++i){p[i]=q.data.front();q.data.pop_front();}q.cv.notify_all();return n;}
static size_t put(void *ctx,const unsigned char *p,size_t n){auto &q=((Transport*)ctx)->output;std::unique_lock<std::mutex> lock(q.mu);q.cv.wait(lock,[&]{return q.data.size()<65536;});n=std::min({n,size_t(65536)-q.data.size(),size_t(3)});q.data.insert(q.data.end(),p,p+n);q.peak=std::max(q.peak,q.data.size());q.cv.notify_all();return n;}
static MYSQL *connect(){MYSQL *m=mysql_init(nullptr);need(m!=nullptr,"mysql_init");mysql_options(m,MYSQL_OPT_USE_EMBEDDED_CONNECTION,nullptr);if(!mysql_real_connect(m,nullptr,"root","",nullptr,0,nullptr,0)){fprintf(stderr,"FAIL:connect %u %s\n",mysql_errno(m),mysql_error(m));std::exit(1);}return m;}
static void query(MYSQL *m,const char *s){if(mysql_query(m,s)){fprintf(stderr,"FAIL:SQL %s %u %s\n",s,mysql_errno(m),mysql_error(m));std::exit(1);}}
static void embedded_prepared(MYSQL *m){
 auto before=mariamem_spike_decode_count();MYSQL_STMT *st=mysql_stmt_init(m);const char *sql="SELECT ?, ?";
 need(!mysql_stmt_prepare(st,sql,strlen(sql)),"embedded prepare");long long n=42,got=0;char s[3]={'a',0,'b'},out[8]={};unsigned long len=3,outlen=0;MYSQL_BIND in[2]={},result[2]={};
 in[0].buffer_type=MYSQL_TYPE_LONGLONG;in[0].buffer=&n;in[1].buffer_type=MYSQL_TYPE_STRING;in[1].buffer=s;in[1].buffer_length=3;in[1].length=&len;
 need(!mysql_stmt_bind_param(st,in),"embedded bind input");need(!mysql_stmt_execute(st),"embedded execute");
 result[0].buffer_type=MYSQL_TYPE_LONGLONG;result[0].buffer=&got;result[1].buffer_type=MYSQL_TYPE_STRING;result[1].buffer=out;result[1].buffer_length=sizeof(out);result[1].length=&outlen;
 need(!mysql_stmt_bind_result(st,result),"embedded bind result");need(!mysql_stmt_store_result(st),"embedded store");need(!mysql_stmt_fetch(st),"embedded fetch");need(got==42&&outlen==3&&!memcmp(s,out,3),"embedded typed result");need(mysql_stmt_fetch(st)==MYSQL_NO_DATA,"embedded one row");need(!mysql_stmt_close(st),"embedded stmt close");need(before==mariamem_spike_decode_count(),"embedded did not use native decode");
 fprintf(stderr,"PASS:embedded_MYSQL_BIND\n");
}
int main(){
 signal(SIGPIPE,SIG_IGN);
 char a0[]="issue65";char a1[]="--no-defaults";char a2[]="--datadir=/exp/temp/data";char a3[]="--skip-grant-tables";char a4[]="--default-storage-engine=MEMORY";char a5[]="--lc-messages-dir=/exp/temp/native/sql/share";char a6[]="--character-set-collations=utf8mb3=uca1400_ai_ci,utf8mb4=uca1400_ai_ci";char *argv[]={a0,a1,a2,a3,a4,a5,a6,nullptr};
 need(!mysql_server_init(7,argv,nullptr),"server init");MYSQL *m=connect();query(m,"CREATE DATABASE test");need(!mysql_select_db(m,"test"),"select test");need(!routine_bootstrap(m,0),"product fresh routine bootstrap");embedded_prepared(m);mysql_close(m);fprintf(stderr,"PASS:product_fresh_bootstrap\n");
 Transport t;
 std::thread reader([&]{unsigned char buf[8192];for(;;){ssize_t n=read(0,buf,sizeof(buf));if(n<0&&errno==EINTR)continue;if(n<=0){std::lock_guard<std::mutex> lock(t.input.mu);t.input.eof=true;t.input.cv.notify_all();return;}size_t pos=0;while(pos<size_t(n)){auto &q=t.input;std::unique_lock<std::mutex> lock(q.mu);q.cv.wait(lock,[&]{return q.data.size()<65536;});size_t z=std::min(size_t(n)-pos,size_t(65536)-q.data.size());q.data.insert(q.data.end(),buf+pos,buf+pos+z);pos+=z;q.peak=std::max(q.peak,q.data.size());q.cv.notify_all();}}});
 std::thread writer([&]{unsigned char buf[8192];for(;;){auto &q=t.output;std::unique_lock<std::mutex> lock(q.mu);q.cv.wait(lock,[&]{return !q.data.empty()||q.eof;});size_t n=std::min(sizeof(buf),q.data.size());if(!n&&q.eof)return;for(size_t i=0;i<n;++i){buf[i]=q.data.front();q.data.pop_front();}q.cv.notify_all();lock.unlock();size_t pos=0;while(pos<n){ssize_t z=write(1,buf+pos,n-pos);if(z<0&&errno==EINTR)continue;if(z<=0)std::_Exit(22);pos+=z;}}});
 for(int i=0;i<2;++i)need(!mariamem_spike_session(&t,get,put),"native session");
 reader.join();{std::lock_guard<std::mutex> lock(t.output.mu);t.output.eof=true;t.output.cv.notify_all();}writer.join();
 m=connect();need(!mysql_select_db(m,"test"),"reopen test");need(!routine_bootstrap(m,1),"product routine structure still valid");embedded_prepared(m);mysql_close(m);mysql_server_end();
 fprintf(stderr,"PASS:all_sessions_retired native_decodes=%lu input_peak=%zu output_peak=%zu\n",mariamem_spike_decode_count(),t.input.peak,t.output.peak);
}
