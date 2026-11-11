/* Compile exact upstream callers against a failing-level-initializer stub.
   No claim that this is a guest OOM or admission test. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
typedef unsigned int uint;
typedef uint my_cs_encoding_t;
typedef int my_bool;
#define MY_UCA_WEIGHT_LEVELS 3
#define MY_CS_NOPAD 1
#define ERROR_LEVEL 1
#define DBUG_ASSERT(x) assert(x)
typedef struct { void *weights; } LEVEL;
typedef struct { LEVEL level[3]; } MY_UCA_INFO;
typedef struct { char error[32]; void *(*once_alloc)(size_t); void (*free)(void*); void (*reporter)(int,const char*,...); } MY_CHARSET_LOADER;
typedef struct { MY_CHARSET_LOADER *loader; MY_UCA_INFO *uca; uint version,strength; void *rule; } MY_COLL_RULES;
typedef struct charset_info_st { const char *tailoring; MY_UCA_INFO *uca; void *casefold,*coll; uint number,levels_for_order,state; } CHARSET_INFO;
static MY_UCA_INFO my_uca_v400,my_uca_v520,my_uca_v1400,my_uca1400_info_tailored[5][1];
static int my_casefold_unicode520,my_casefold_unicode1400,my_casefold_default;
static int my_uca_collation_handler_nopad_multilevel_generic,my_uca_collation_handler_multilevel_generic;
static const struct { uint collation_id; } mysql_0900_mapping[]= {{2304}};
static const uint mysql_0900_collation_start=255;
static uint init_calls, fail_init;
static int weight_stub;
static my_cs_encoding_t my_uca1400_collation_id_to_charset_id(uint id) { return (id-2048)/256; }
static uint my_uca1400_collation_id_to_tailoring_id(uint id) { (void)id;return 0; }
static int my_collation_id_is_uca1400(uint id) { return id>=2048 && id<4096; }
static int my_collation_id_is_mysql_uca0900(uint id) { return id==255; }
static int my_coll_rule_parse(MY_COLL_RULES *rules,const char *start,const char *end) { (void)start;(void)end;rules->version=1400;return 0; }
static void my_ci_set_strength(CHARSET_INFO *cs,uint strength) {cs->levels_for_order=strength;}
static int my_uca_info_init(MY_CHARSET_LOADER *loader,MY_UCA_INFO *dst,MY_COLL_RULES *rules,CHARSET_INFO *cs,const MY_UCA_INFO *src,uint levels) {
  (void)loader;(void)rules;(void)cs;(void)src;(void)levels;
  init_calls++;dst->level[0].weights=&weight_stub;return fail_init;
}
#include "caller-functions.h"
int main(void) {
  MY_CHARSET_LOADER loader={{0},malloc,free,NULL};
  for(uint route=0;route<2;route++) {
    memset(my_uca1400_info_tailored,0,sizeof(my_uca1400_info_tailored));
    CHARSET_INFO cs={.tailoring="",.uca=&my_uca_v1400,.number=route?255:2304};
    init_calls=0;fail_init=1;
    int first=create_tailoring(&cs,&loader);
    assert(cs.uca==NULL && init_calls==1);
    fail_init=0;
    int second=create_tailoring(&cs,&loader);
    assert(second==0 && cs.uca!=NULL);
#ifdef EXPECT_ORIGINAL_BUG
    assert(first==0 && init_calls==1);
#else
    assert(first!=0 && init_calls==2);
#endif
  }
#ifdef EXPECT_ORIGINAL_BUG
  puts("Original false-success and incomplete-cache reuse reproduced on both caller routes");
#else
  puts("Failure propagated and retry reinitializes on both caller routes");
#endif
  return 0;
}
