// Compile/link/import probe only; no MariaDB, transport or runtime acceptance.
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <thread>

struct MemoryCallback {
  void *context;
  unsigned (*read)(void *, unsigned char *, unsigned);
};
static std::mutex mutex;
static std::condition_variable changed;
static bool ready;
static unsigned result;
static unsigned read_one(void *context,unsigned char *out,unsigned size) {
  if (!size) return 0;
  *out=*static_cast<unsigned char *>(context);return 1;
}
extern "C" __attribute__((noinline,export_name("probe_callback")))
unsigned probe_callback(MemoryCallback *io,unsigned char *out) {
  return io->read(io->context,out,1);
}
int main() {
  unsigned char source=42,output=0;
  MemoryCallback io{&source,read_one};
  std::thread worker([&] {
    std::unique_lock<std::mutex> lock(mutex);
    changed.wait(lock,[]{return ready;});
    result=probe_callback(&io,&output);
  });
  {
    std::unique_lock<std::mutex> lock(mutex);
    if(changed.wait_until(lock,std::chrono::steady_clock::now()+std::chrono::milliseconds(1),[]{return ready;}))return 2;
    ready=true;
  }
  changed.notify_all();worker.join();
  std::printf("callback=%u byte=%u\n",result,unsigned(output));
  return result==1&&output==42?0:3;
}
