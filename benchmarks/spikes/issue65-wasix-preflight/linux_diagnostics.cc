#include <execinfo.h>
int main(){void *frames[4];return backtrace(frames,4);}
