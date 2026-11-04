import sys
from pathlib import Path
import difflib,json,hashlib
w=Path(sys.argv[1]).resolve();t=w/'temp';s=t/'source';u=next((t/'upstream').iterdir());e=w/'evidence'
c=(u/'strings/ctype-uca.c').read_text();h=(u/'include/m_ctype.h').read_text();c2=c.replace('#include "my_bit.h"','#include "my_bit.h"\n#if defined(__wasi__)\n#include "mariamem_uca_prepared.h"\n#endif',1)
old='''static MY_UCA_LEVEL_BOOSTER *
my_uca_level_booster_new(MY_CHARSET_LOADER *loader,
                         CHARSET_INFO *cs,
                         MY_UCA_WEIGHT_LEVEL *level)
{
  MY_UCA_LEVEL_BOOSTER *res;
'''
new='''static const MY_UCA_LEVEL_BOOSTER *
my_uca_level_booster_new(MY_CHARSET_LOADER *loader,
                         CHARSET_INFO *cs,
                         MY_UCA_WEIGHT_LEVEL *level)
{
  MY_UCA_LEVEL_BOOSTER *res;
#if defined(__wasi__)
  /* Experiment: exact built-in UCA1400 default PAD ai_ci identities only.
     Other encodings/tailorings/aliases retain the original producer. */
  if ((cs->number == 2048 || cs->number == 2304) && level->levelno < 3 &&
      level == &my_uca1400_info_tailored[
                  my_uca1400_collation_id_to_charset_id(cs->number)][0].level[level->levelno])
  {
    const MY_UCA_LEVEL_BOOSTER *cached= &prepared[level->levelno];
    /* Mandatory separate verification run, disabled in timing runs. */
    if (getenv("MARIAMEM_GUEST_TIMING"))
    {
      int match;
      if (!(res= my_uca_level_booster_alloc(loader)))
        abort();
      my_uca_level_booster_populate(res, level, cs);
      match= memcmp(res, cached, sizeof(*res)) == 0;
      fprintf(stderr, "UCA_PREPARED_VERIFY id=%u level=%u bytes=%u match=%d\\n",
              cs->number, level->levelno, (unsigned) sizeof(*res), match);
      if (!match)
        abort();
    }
    return cached;
  }
#endif
'''
assert c2.count(old)==1;c2=c2.replace(old,new,1)
oldh='  MY_UCA_LEVEL_BOOSTER *booster;';assert h.count(oldh)==1;h2=h.replace(oldh,'  const MY_UCA_LEVEL_BOOSTER *booster;',1)
header=(t/'prepared.h').read_text();out=''
for name,before,after in [('include/m_ctype.h',h,h2),('strings/ctype-uca.c',c,c2),('strings/mariamem_uca_prepared.h','',header)]:out+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name if before else '/dev/null',tofile='b/'+name))
(s/'guest/experimental.patch').write_text(out)
(t/'candidate-ctype-uca.c').write_text(c2);(t/'candidate-m_ctype.h').write_text(h2)
(e/'patch.json').write_text(json.dumps({'sha256':hashlib.sha256(out.encode()).hexdigest(),'selected_ids':[2048,2304],'levels':[0,1,2],'unmatched':'original allocation/populate function','verify_env':'host MARIAMEM_TIMING_DIR enables existing guest MARIAMEM_GUEST_TIMING; mandatory untimed guest run requires all six matches','header_sha256':hashlib.sha256(header.encode()).hexdigest(),'static_data_bytes':2754048,'readonly_pointer_field':True,'canonical_source_patch_modified':False},indent=2)+'\n')
print('candidate experimental patch written',len(out),'bytes')
