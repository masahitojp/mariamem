import sys
from pathlib import Path
import re,subprocess,json,os,hashlib
w=Path(sys.argv[1]).resolve();t=w/'temp';e=w/'evidence';u=next((t/'upstream').iterdir());c=(t/'candidate-ctype-uca.c').read_text();orig=(u/'strings/ctype-uca.c').read_text()
def through(text,start):
 a=text.index(start);brace=text.index('{',a);i=brace+1;depth=1
 while depth:
  if text[i]=='{':depth+=1
  if text[i]=='}':depth-=1
  i+=1
 return text[a:i]+'\n'
alloc=through(orig,'static MY_UCA_LEVEL_BOOSTER *\nmy_uca_level_booster_alloc(');new=through(c,'static const MY_UCA_LEVEL_BOOSTER *\nmy_uca_level_booster_new(')
text='''#define main generator_main
#include "producer.c"
#undef main
#include "prepared.h"
MY_UCA_INFO my_uca1400_info_tailored[MY_CS_ENCODING_LAST+1][MY_UCA1400_COLLATION_DEFINITION_COUNT];
'''+alloc+'\n'+new+'''
static int calls;
static void *once(size_t n) { calls++;return calloc(1,n); }
int main(void) {
 MY_CHARSET_HANDLER handlers[2]={{.mb_wc=decode3,.wc_mb=my_uni_utf8mb3},{.mb_wc=decode4,.wc_mb=my_wc_mb_utf8mb4}};
 MY_CHARSET_LOADER loader={.once_alloc=once};
 for(uint enc=0;enc<2;enc++) {
  my_uca1400_info_tailored[enc][0]=my_uca_v1400;
  struct charset_info_st cs={.number=enc?2304:2048,.cset=&handlers[enc]};
  for(uint level=0;level<3;level++) {
   MY_UCA_WEIGHT_LEVEL *l=&my_uca1400_info_tailored[enc][0].level[level];
   int before=calls;
   const MY_UCA_LEVEL_BOOSTER *b=my_uca_level_booster_new(&loader,&cs,l);
   if(b!=&prepared[level] || (!getenv("MARIAMEM_UCA_PREPARED_VERIFY") && calls!=before))return 80;
   MY_UCA_WEIGHT_LEVEL detached=*l;
   b=my_uca_level_booster_new(&loader,&cs,&detached);if(b==&prepared[level])return 81;free((void*)b);
   cs.number=enc?2312:2056;
   b=my_uca_level_booster_new(&loader,&cs,l);if(b==&prepared[level])return 82;free((void*)b);
   cs.number=enc?2304:2048;
  }
 }
 return 0;
}
'''
(t/'check-constructor.c').write_text(text)
base=['cc','-O2','-g','-fsanitize=address,undefined','-D__wasi__','-DHAVE_CHARSET_utf8mb4','-DDISABLE_MYSQL_THREAD_H','-I'+str(t/'config'),'-I'+str(u/'include'),'-I'+str(u/'strings')]
p=subprocess.run(base+[str(t/'check-constructor.c'),'-o',str(t/'check-constructor')],capture_output=True,text=True);(e/'constructor-build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0') # once_alloc has process lifetime; no live DB owner in this stand-alone tool.
for mode in ['timing-path','verify-path']:
 env.pop('MARIAMEM_UCA_PREPARED_VERIFY',None)
 if mode=='verify-path':env['MARIAMEM_UCA_PREPARED_VERIFY']='1'
 p=subprocess.run([str(t/'check-constructor')],env=env,capture_output=True,text=True);(e/(mode+'.log')).write_text(p.stdout+p.stderr);assert p.returncode==0,(mode,p.stderr)
 if mode=='verify-path':assert p.stderr.count('match=1')==6,p.stderr
(e/'constructor-check.json').write_text(json.dumps({'result':'PASS_NATIVE_ONLY','actual_candidate_constructor_compiled':True,'exact_table_hits':6,'detached_level_fallbacks':6,'different_tailoring_fallbacks':6,'verification_full_memcmp_matches':6,'fastpath_dynamic_allocation_calls':0,'sanitizers':'ASan+UBSan; native standalone once_alloc leak detection disabled because storage intentionally lasts process lifetime','guest_runtime':'UNVERIFIED'},indent=2)+'\n');print('actual constructor native fast/verify/fallback paths PASS')
