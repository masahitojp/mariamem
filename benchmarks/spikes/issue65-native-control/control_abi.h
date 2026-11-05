#pragma once
#include <cstddef>
#include <cstdint>
enum SpikeEvent { REGISTER_THD=1, AUTH_COMPLETE=2, ARM_COMMAND=3,
  EXECUTE_START=4, COMMAND_COMPLETE=5, CONNECTION_COMPLETE=6, UNREGISTER_THD=7 };
struct SpikeIO {
 void *ctx;
 size_t (*read)(void*,unsigned char*,size_t);
 size_t (*write)(void*,const unsigned char*,size_t);
 int (*error)(void*);
 int (*wait)(void*,int,int);
 void (*close)(void*);
 int (*event)(void*,int,void*,unsigned);
};
extern "C" int mariamem_spike_control_session(SpikeIO*);
extern "C" void mariamem_spike_kill(void*);
extern "C" unsigned long mariamem_spike_decode_count();
