import sys
from pathlib import Path
import json,hashlib,re,subprocess
w=Path(sys.argv[1]).resolve();t=w/'temp';u=next((t/'upstream').iterdir());cfg=t/'config';c=(u/'strings/ctype-uca.c').read_text();utf=(u/'strings/ctype-utf8.c').read_text();src1400=(u/'strings/ctype-uca1400.c').read_text()
def function(text,name):
 m=re.search(r'(?:static (?:inline )?(?:int|size_t|void|my_bool)\s*\n?\s*)'+name+r'\(',text);assert m,name
 begin=text.index('{',m.start());depth=1;i=begin+1
 while depth:
  if text[i]=='{':depth+=1
  elif text[i]=='}':depth-=1
  i+=1
 return text[m.start():i]+'\n'
start=c.index('static size_t\nmy_uca_weight_cpy(');end=c.index('static MY_UCA_LEVEL_BOOSTER *\nmy_uca_level_booster_alloc(');block=c[start:end]
start=src1400.index('MY_UCA_INFO my_uca_v1400=');end=src1400.index('\n};',start)+3;initializer=src1400[start:end]
text='''#include "strings_def.h"
#include "ctype-uca.h"
#include "ctype-utf8.h"
#include "ctype-uca1400data.h"
#include <stdio.h>
#include <stddef.h>
_Static_assert(sizeof(uint16)==2, "uint16 width");
_Static_assert(sizeof(MY_UCA_LEVEL_BOOSTER)==918016, "booster layout");
_Static_assert(offsetof(MY_UCA_LEVEL_BOOSTER,weight_strings_2bytes_to_1_or_2_weights)==655360,"field2 offset");
_Static_assert(offsetof(MY_UCA_LEVEL_BOOSTER,weight_1byte_to_1weight_standalone)==917504,"field3 offset");
'''+initializer+'\n'+function(utf,'my_uni_utf8mb3')+'\n'+function(utf,'my_wc_mb_utf8mb4')+'''
static int decode3(CHARSET_INFO *cs, my_wc_t *wc,const uchar *s,const uchar *e) { return my_mb_wc_utf8mb3_quick(wc,s,e); }
static int decode4(CHARSET_INFO *cs, my_wc_t *wc,const uchar *s,const uchar *e) { return my_mb_wc_utf8mb4_quick(wc,s,e); }
'''+block+'''
int main(int argc,char **argv) {
 if (argc!=2) return 2;
 MY_CHARSET_HANDLER handlers[2] = {{.mb_wc=decode3,.wc_mb=my_uni_utf8mb3},{.mb_wc=decode4,.wc_mb=my_wc_mb_utf8mb4}};
 for(int encoding=0;encoding<2;encoding++) {
  CHARSET_INFO cs={.cset=&handlers[encoding]};
  for(int level=0;level<3;level++) {
   MY_UCA_LEVEL_BOOSTER *b=calloc(1,sizeof(*b));if(!b)return 3;
   my_uca_level_booster_populate(b,&my_uca_v1400.level[level],&cs);
   char name[4096];snprintf(name,sizeof(name),"%s/utf8mb%d-level%d.bin",argv[1],encoding+3,level);
   FILE *f=fopen(name,"wb");if(!f)return 4;
   if(fwrite(b,1,sizeof(*b),f)!=sizeof(*b))return 5;
   if(fclose(f))return 6;free(b);
  }
 }
 return 0;
}
'''
(t/'producer.c').write_text(text)
cmd=['cc','-O2','-g','-fsanitize=address,undefined','-DHAVE_CHARSET_utf8mb4','-DDISABLE_MYSQL_THREAD_H','-I'+str(cfg),'-I'+str(u/'include'),'-I'+str(u/'strings'),str(t/'producer.c'),'-o',str(t/'producer')]
p=subprocess.run(cmd,text=True,capture_output=True);(w/'evidence/producer-build.log').write_text(p.stdout+p.stderr);(w/'evidence/producer-command.json').write_text(json.dumps(cmd,indent=2)+'\n');(w/'evidence/extraction.json').write_text(json.dumps({'source_sha256':hashlib.sha256((u/'strings/ctype-uca.c').read_bytes()).hexdigest(),'producer_block_sha256':hashlib.sha256(block.encode()).hexdigest(),'initial_uca_info_sha256':hashlib.sha256(initializer.encode()).hexdigest(),'utf8_encoders_sha256':{n:hashlib.sha256(function(utf,n).encode()).hexdigest() for n in ['my_uni_utf8mb3','my_wc_mb_utf8mb4']},'scope':'verbatim producer/initializer/encoders; original full headers; only main and decoder signature adapters are glue'},indent=2)+'\n');print(p.stderr[-6500:]);raise SystemExit(p.returncode)
