#pragma once
// Transport component fixture only. No SQL engine or THD is emulated.
constexpr unsigned COM_QUIT=1;
inline int mysql_thread_init(){return 0;}
inline void mysql_thread_end(){}
