import sys
from pathlib import Path
import struct,subprocess,json,hashlib,time
w=Path(sys.argv[1]).resolve();t=w/'temp';e=w/'evidence';u=next((t/'upstream').iterdir());header=t/'prepared.h'
parts=['static const MY_UCA_LEVEL_BOOSTER prepared[3] = {\n']
for level in range(3):
 values=struct.unpack('<459008H',(t/f'tables-a/utf8mb3-level{level}.bin').read_bytes());assert len(values)==459008
 def rows(v,width):return ',\n'.join('{{'+','.join(map(str,v[i:i+width]))+'}}' for i in range(0,len(v),width))
 parts+=['{\n{'+rows(values[:327680],5)+'},\n{'+rows(values[327680:458752],2)+'},\n{'+','.join(map(str,values[458752:]))+'}\n},\n']
parts+=['};\n'];header.write_text(''.join(parts))
checker=r'''
#define main generator_main
#include "producer.c"
#undef main
#ifndef PREPARED_HEADER
#define PREPARED_HEADER "prepared.h"
#endif
#include PREPARED_HEADER
static const MY_UCA_LEVEL_BOOSTER *select_prepared(uint id,uint uca_version,uint level) {
 /* Native prototype: only exact default PAD ai_ci IDs, fixed UCA1400 source.
    Broader aliases/custom definitions and runtime integration remain unverified. */
 if ((id!=2048 && id!=2304) || uca_version!=1400 || level>=3) return NULL;
 return &prepared[level];
}
int main(void) {
 MY_CHARSET_HANDLER handlers[2]={{.mb_wc=decode3,.wc_mb=my_uni_utf8mb3},{.mb_wc=decode4,.wc_mb=my_wc_mb_utf8mb4}};
 for(uint enc=0;enc<2;enc++) {
  CHARSET_INFO cs={.cset=&handlers[enc]};
  for(uint level=0;level<3;level++) {
   MY_UCA_LEVEL_BOOSTER *b=calloc(1,sizeof(*b));if(!b)return 3;
   my_uca_level_booster_populate(b,&my_uca_v1400.level[level],&cs);
   const MY_UCA_LEVEL_BOOSTER *cached=select_prepared(enc?2304:2048,1400,level);
   if(!cached || memcmp(b,cached,sizeof(*b)))return 88;
   free(b);
  }
 }
 uint bad_ids[]={0,33,45,255,2049,2056,2305,2312,2560,2816,3072,4096};
 for(size_t i=0;i<sizeof(bad_ids)/sizeof(*bad_ids);i++)if(select_prepared(bad_ids[i],1400,0))return 89;
 if(select_prepared(2048,520,0)||select_prepared(2304,1400,3)||select_prepared(2048,1400,(uint)-1))return 90;
 puts("PASS six full-table memcmp checks; unmatched ID/version/level selects original-path fallback");
 return 0;
}
'''
(t/'check-prepared.c').write_text(checker)
base=['cc','-O2','-g','-fsanitize=address,undefined','-DHAVE_CHARSET_utf8mb4','-DDISABLE_MYSQL_THREAD_H','-I'+str(t/'config'),'-I'+str(u/'include'),'-I'+str(u/'strings')]
start=time.monotonic();p=subprocess.run(base+[str(t/'check-prepared.c'),'-o',str(t/'check-prepared')],capture_output=True,text=True);(e/'prepared-build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr[-3000:]
p=subprocess.run([str(t/'check-prepared')],capture_output=True,text=True);(e/'prepared-check.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
# Change one valid numeric table cell without changing C layout or parser shape.
s=header.read_text();startcell=s.index('{{')+2
while s[startcell]=='{':startcell+=1
endcell=s.index(',',startcell);old=int(s[startcell:endcell]);mutated=s[:startcell]+str(old^1)+s[endcell:];(t/'prepared-mutated.h').write_text(mutated)
cmd=base+['-DPREPARED_HEADER="prepared-mutated.h"',str(t/'check-prepared.c'),'-o',str(t/'check-prepared-mutated')];q=subprocess.run(cmd,capture_output=True,text=True);assert q.returncode==0,q.stderr[-3000:]
q=subprocess.run([str(t/'check-prepared-mutated')],capture_output=True,text=True);assert q.returncode==88,(q.returncode,q.stderr)
result={'result':'NATIVE_FIXED_INPUT_PRECOMPUTED_ROUNDTRIP_PASS','full_table_comparisons':6,'unmatched_selector_cases':15,'one_cell_corruption_rejected':True,'sanitizers':'ASan+UBSan clean','typed_const_header_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'typed_const_header_bytes':header.stat().st_size,'distinct_static_table_bytes':3*918016,'elapsed_build_and_checks_seconds':time.monotonic()-start,'limitations':['not yet guest build or runtime post-tailoring byte parity','selector model matches only exact two IDs; no general collation support claim','native tool timing not a Fork benchmark']}
(e/'prepared-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
