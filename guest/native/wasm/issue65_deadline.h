#ifndef MARIAMEM_ISSUE65_DEADLINE_H
#define MARIAMEM_ISSUE65_DEADLINE_H
#include <chrono>
#include <cstdint>
#include <limits>
#include <ratio>
#include <type_traits>
namespace issue65_deadline {
using Clock=std::chrono::steady_clock;
static_assert(std::ratio_equal<Clock::period,std::nano>::value,"nanosecond steady clock required");
static_assert(sizeof(Clock::rep)==8 && std::is_signed<Clock::rep>::value,"signed64 steady clock required");
constexpr uint64_t maximum=uint64_t(std::numeric_limits<int64_t>::max());
constexpr bool valid(uint64_t ns){return ns!=0 && ns<=maximum;}
// Unsigned elapsed ticks avoid now+timeout overflow,including signed-clock wrap.
constexpr bool elapsed(uint64_t now,uint64_t start,uint64_t ns){return now-start>=ns;}
inline uint64_t ticks(Clock::time_point now){return uint64_t(now.time_since_epoch().count());}
struct Budget {
 const uint64_t limit;
 uint64_t start;
 bool armed=true;
 explicit Budget(uint64_t ns):limit(ns),start(ticks(Clock::now())){}
 void arm(Clock::time_point now){start=ticks(now);armed=true;}
 void disarm(){armed=false;}
 bool expired(Clock::time_point now)const{return armed&&elapsed(ticks(now),start,limit);}
};
}
#endif
