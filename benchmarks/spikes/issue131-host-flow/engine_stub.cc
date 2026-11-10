// Drive the actual controller callbacks; not MariaDB/runtime acceptance.
#include "mariamem_control_abi.h"
#include <algorithm>
#include <array>
extern "C" int issue65_bootstrap(){return 0;}
extern "C" void issue65_shutdown(){}
extern "C" void mariamem_spike_kill(void*){}
extern "C" unsigned long mariamem_spike_decode_count(){return 0;}
extern "C" int mariamem_spike_control_session(SpikeIO *io){
 int handle=0,result=0;
 io->event(io->ctx,REGISTER_THD,&handle,0);
 if(io->event(io->ctx,AUTH_COMPLETE,&handle,2))result=1;
 while(!result){
  if(io->event(io->ctx,ARM_COMMAND,&handle,2)){result=2;break;}
  unsigned char cmd=0;size_t got=io->read(io->ctx,&cmd,1);
  if(got!=1){io->event(io->ctx,CONNECTION_COMPLETE,&handle,2);break;}
  if(io->event(io->ctx,EXECUTE_START,&handle,cmd=='Q'?1:3)){result=3;break;}
  if(cmd=='Q'){io->event(io->ctx,CONNECTION_COMPLETE,&handle,2);break;}
  size_t length=cmd=='B'?262144:cmd=='F'?70000:1;
  std::array<unsigned char,4096> bytes{};size_t offset=0;
  while(offset<length){
   size_t count=std::min(length-offset,cmd=='F'?size_t(1):bytes.size());
   for(size_t i=0;i<count;++i)bytes[i]=(offset+i)%251;
   size_t n=io->write(io->ctx,bytes.data(),count);
   if(n==size_t(-1)||!n){result=4;break;}offset+=n;
  }
  if(!result&&io->event(io->ctx,COMMAND_COMPLETE,&handle,2))result=5;
 }
 io->event(io->ctx,UNREGISTER_THD,&handle,0);
 io->event(io->ctx,CLEANUP_RESULT,&handle,0);
 return result;
}
