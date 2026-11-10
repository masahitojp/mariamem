"""Read-only partition of a single observed embedded startup."""
from decompose import events,decompose
BUCKETS=['timer','locale','lex','functions','json']
def partition(trace):
 s=trace['startup'];es=events(s['events'])
 begin,end=[es['common_'+n] for n in ['begin','end']]
 assert end>=begin
 intervals=[];out={}
 for key in BUCKETS:
  a,b=[es['common_'+key+'_'+n] for n in ['begin','end']]
  assert begin<=a<=b<=end,(key,begin,a,b,end)
  intervals.append((a,b));out[key]=b-a
 assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),intervals
 out['total']=end-begin
 out['other']=out['total']-sum(out[k] for k in BUCKETS)
 assert out['other']>=0
 out['literal_lengths']=out['locale']+out['lex']
 out['lookups']=out['functions']+out['json']
 a,b=[es['common_charset_'+n] for n in ['begin','end']]
 assert a<=b
 out['charset_inclusive']=b-a
 out['charset_within_common']=max(0,min(b,end)-max(a,begin))
 assert begin<=a<=b<=end
 assert all(b<=x or y<=a for x,y in intervals), 'charset overlaps named bucket'
 out['other_excluding_charset']=out['other']-(b-a)
 assert out['other_excluding_charset']>=0
 out['after_charset']=end-b
 out['before_timer']=es['common_timer_begin']-begin
 out['between_timer_locale']=es['common_locale_begin']-es['common_timer_end']
 out['between_locale_lex']=es['common_lex_begin']-es['common_locale_end']
 out['between_json_charset']=a-es['common_json_end']
 out['guest_common']=decompose(trace)['common']
 out['host_minus_guest']=out['total']-out['guest_common']
 timer=s['common_timer'];assert len(timer)==20
 out['clock_metadata']={key:dict(zip(['routine','overhead','frequency','resolution'],timer[i*4:i*4+4])) for i,key in enumerate(['cycles','nanoseconds','microseconds','milliseconds','ticks'])}
 return out
