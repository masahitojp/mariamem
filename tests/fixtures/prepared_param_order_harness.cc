/* Extracted MariaDB source functions with mock dependencies. This proves
 * descriptor assignment order, not the engine's complete conversion behavior.
 * The upstream GPLv2 copyright/license notice is retained in the JSON fixture. */
#include <assert.h>
#include <stdio.h>
#define DBUG_ENTER(x) ((void)0)
#define DBUG_RETURN(x) return (x)
using uchar=unsigned char;
using ulong=unsigned long;
struct String {};
struct MYSQL_BIND {unsigned buffer_type;bool is_unsigned,*is_null;void *buffer;
 ulong *length,buffer_length;};
struct THD {MYSQL_BIND *client_params;};
struct Item_param {
 bool unsigned_flag=false,seen_unsigned=false,is_null=false,conversion_error=false;
 unsigned conversions=0;
 void setup_conversion(THD *,unsigned){seen_unsigned=unsigned_flag;conversions++;}
 bool has_long_data_value(){return false;}
 void set_null(){is_null=true;}
 void set_param_func(uchar **,ulong){is_null=false;}
 bool has_no_value(){return false;}
 void sync_clones(){}
 bool convert_str_value(THD *){return conversion_error;}
};
struct Prepared_statement {
 THD *thd;Item_param **param_array;unsigned param_count;
 const char *query(){return "SELECT ?";}
 unsigned query_length(){return 8;}
};
struct Copy_query_with_rewrite {
 Copy_query_with_rewrite(THD *,const char *,unsigned,String *){}
 bool append(Item_param *){return false;}
 bool finalize(){return false;}
};
#include "param-functions.inc"

int main(){
 unsigned matching=0;
 bool flags[]={false,true};
 for(bool logging:flags)for(bool requested:flags)for(bool null_value:flags){
  Item_param p;p.unsigned_flag=!requested;Item_param *params[]={&p};
  ulong length=4;unsigned value=17;MYSQL_BIND bind={3,requested,&null_value,&value,&length,4};
  THD thd={&bind};Prepared_statement stmt={&thd,params,1};String output;
  assert(!(logging?emb_insert_params_with_log(&stmt,&output):emb_insert_params(&stmt,&output)));
  assert(p.conversions==1&&p.is_null==null_value);
  if(p.seen_unsigned==requested&&p.unsigned_flag==requested)matching++;
  p.conversion_error=true;
  assert(logging?emb_insert_params_with_log(&stmt,&output):emb_insert_params(&stmt,&output));
 }
 printf("{\"matching_descriptors\":%u,\"cases\":8,\"scope\":\"extracted parameter functions with mock dependencies\"}\n",matching);
}
