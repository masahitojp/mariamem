/* Source-level harness only: scalar WASM32 layout, native pointers/allocator.
   It is not an engine or a guest acceptance test. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "m_ctype.h"
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"CHECK failed: %s\n",#x); exit(2); } } while(0)
typedef struct { void *(*once_alloc)(size_t); } MY_CHARSET_LOADER;
typedef struct { uint number; const char *tailoring; } CHARSET_INFO;
typedef struct { size_t nrules; } MY_COLL_RULES;
typedef struct {
  my_wc_t maxchar;
  uchar *lengths;
  uint16 **weights;
  MY_CONTRACTIONS contractions;
  uint levelno;
  MY_UCA_CONTRACTION_HASH contraction_hash;
  const void *booster;
} MY_UCA_WEIGHT_LEVEL;
typedef struct { MY_UCA_WEIGHT_LEVEL level[3]; } MY_UCA_INFO;
static MY_UCA_INFO my_uca_v1400;
static MY_UCA_INFO my_uca1400_info_tailored[5][1];
static uint my_uca1400_collation_id_to_charset_id(uint id) { return (id-2048)/256; }
static void *owned[64];
static size_t owned_count, alloc_count, fail_at;
static void *allocate(size_t size) {
  alloc_count++;
  if (fail_at && alloc_count == fail_at) return NULL;
  CHECK(owned_count < array_elements(owned));
  void *p= malloc(size); CHECK(p); memset(p, 0xA5, size);
  owned[owned_count++]= p; return p;
}
static void cleanup(void) {
  while (owned_count) free(owned[--owned_count]);
  alloc_count= fail_at= 0;
  memset(my_uca1400_info_tailored,0,sizeof(my_uca1400_info_tailored));
}
#include "contractions.h"
#include "reference.h"
#include "prepared.h"
#include "copy.c"
static void original(MY_CHARSET_LOADER *loader, MY_UCA_WEIGHT_LEVEL *dst,
                     const MY_UCA_WEIGHT_LEVEL *src) {
  size_t i;
  CHECK(!my_uca_alloc_contractions(&dst->contractions,loader,src->contractions.nitems));
  for (i= 0; i != src->contractions.nitems; i++)
  {
    MY_CONTRACTION *item= &src->contractions.item[i];
    size_t length= my_wstrnlen(item->ch, array_elements(item->ch));
    uint16 *weights= my_uca_init_one_contraction(&dst->contractions,
                                                 item->ch, length,
                                                 item->with_context);
    memcpy(weights, item->weight, sizeof(item->weight));
  }
  CHECK(!my_uca_contraction_hash_allocate(&dst->contraction_hash,loader));
  CHECK(!my_uca_contraction_hash_populate(&dst->contraction_hash,&dst->contractions));
}
static void equal(MY_UCA_WEIGHT_LEVEL *a, MY_UCA_WEIGHT_LEVEL *b) {
  CHECK(a->contractions.nitems == b->contractions.nitems);
  CHECK(a->contraction_hash.nitems_alloced == b->contraction_hash.nitems_alloced);
  CHECK(!memcmp(a->contractions.item,b->contractions.item,939*sizeof(MY_CONTRACTION)));
  CHECK(!memcmp(a->contractions.flags,b->contractions.flags,4096));
  CHECK(!memcmp(a->contraction_hash.item,b->contraction_hash.item,4096*sizeof(MY_CONTRACTION)));
}
int main(void) {
  uint32_t endian= 1; CHECK(*(unsigned char*)&endian == 1);
  MY_CONTRACTION *source_items[3]= {uca1400_contractions,uca1400_contractions_secondary,uca1400_contractions_tertiary};
  MY_CHARSET_LOADER loader= {allocate}; MY_COLL_RULES rules= {0};
  for (uint l=0;l<3;l++) {
    my_uca_v1400.level[l].maxchar=0x10FFFF; my_uca_v1400.level[l].levelno=l;
    my_uca_v1400.level[l].contractions.item=source_items[l];
    my_uca_v1400.level[l].contractions.nitems=939;
    MY_UCA_WEIGHT_LEVEL reference= {0}; original(&loader,&reference,&my_uca_v1400.level[l]);
    CHECK(fwrite(reference.contractions.item,sizeof(MY_CONTRACTION),939,stdout)==939);
    CHECK(fwrite(reference.contractions.flags,1,4096,stdout)==4096);
    CHECK(fwrite(reference.contraction_hash.item,sizeof(MY_CONTRACTION),4096,stdout)==4096);
    for (uint e=0;e<5;e++) {
      CHARSET_INFO cs= {2048+e*256,""};
      MY_UCA_WEIGHT_LEVEL *dst=&my_uca1400_info_tailored[e][0].level[l];
      CHECK(mariamem_uca_copy_default(&loader,&cs,&rules,dst,&my_uca_v1400.level[l])==1);
      equal(dst,&reference);
      CHECK(dst->contractions.item!=reference.contractions.item);
      CHECK(dst->contractions.item!=source_items[l]);
      CHECK(dst->contraction_hash.item!=mariamem_uca_copy_hash[l]);
    }
    MY_UCA_WEIGHT_LEVEL *a=&my_uca1400_info_tailored[0][0].level[l];
    MY_UCA_WEIGHT_LEVEL *b=&my_uca1400_info_tailored[1][0].level[l];
    CHECK(a->contractions.item!=b->contractions.item && a->contractions.flags!=b->contractions.flags && a->contraction_hash.item!=b->contraction_hash.item);
    a->contractions.item[0].weight[0]^=1; a->contractions.flags[0]^=1; a->contraction_hash.item[0].ch[0]^=1;
    equal(b,&reference); cleanup();
  }
  CHARSET_INFO cs={2048,""}; MY_UCA_WEIGHT_LEVEL *src=&my_uca_v1400.level[0];
  MY_UCA_WEIGHT_LEVEL *dst=&my_uca1400_info_tailored[0][0].level[0];
  for (size_t fail=1;fail<=3;fail++) {
    fail_at=fail; CHECK(mariamem_uca_copy_default(&loader,&cs,&rules,dst,src)==-1);
    CHECK(alloc_count==fail && owned_count==fail-1);
    CHECK(!dst->contractions.item && !dst->contractions.flags && !dst->contraction_hash.item);
    CHECK(!dst->contractions.nitems && !dst->contraction_hash.nitems_alloced); cleanup();
  }
  for (uint n=0;n<9;n++) {
    MY_UCA_WEIGHT_LEVEL other=*src; MY_UCA_WEIGHT_LEVEL *s=src, *d=dst;
    cs.number=2048;cs.tailoring="";rules.nrules=0;
    if(n==0) cs.number=2049;
    if(n==1) cs.tailoring=NULL;
    if(n==2) cs.tailoring="&a<b";
    if(n==3) rules.nrules=1;
    if(n==4) s=&other;
    if(n==5) d=&other;
    if(n==6) src->levelno=3;
    if(n==7) src->maxchar=0xFFFF;
    if(n==8) src->contractions.nitems=938;
    CHECK(mariamem_uca_copy_default(&loader,&cs,&rules,d,s)==0);
    CHECK(alloc_count==0 && owned_count==0);
    src->levelno=0;src->maxchar=0x10FFFF;src->contractions.nitems=939;
  }
  CHECK(fflush(stdout)==0);
  fprintf(stderr,"15 profile/level copies, 3 ownership mutations, 3 allocation failures, 9 guard misses PASS\n");
  return 0;
}
