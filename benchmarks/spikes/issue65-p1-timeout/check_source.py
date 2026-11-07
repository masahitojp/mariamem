#!/usr/bin/env python3
"""Compile actual prepared source seams with small dependency stubs,not an engine qualification."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path

def function(text,name):
    match=re.search(r'(?:static bool\s+|bool\s+)'+re.escape(name)+r'\s*\(',text)
    if not match:raise ValueError('missing '+name)
    start=match.start();at=text.index('{',match.end());depth=1;end=at+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    source=a.source.read_text()
    pin=json.loads((Path(__file__).parent/'source-audit.json').read_text())['patched_sql_prepare_sha256']
    if hashlib.sha256(a.source.read_bytes()).hexdigest()!=pin:raise ValueError('prepared source differs from audited full patched source')
    a.output.mkdir(parents=True,exist_ok=True)
    names=['parameter_type_sanity_check','stmt_execute_packet_sanity_check','mariamem_wire_null_fallback','insert_params','insert_params_with_log']
    actual={name:function(source,name) for name in names}
    # Values are protocol enum constants,not a replacement parameter decoder.
    values=dict(DECIMAL=0,TINY=1,SHORT=2,LONG=3,FLOAT=4,DOUBLE=5,NULL=6,TIMESTAMP=7,LONGLONG=8,INT24=9,DATE=10,TIME=11,DATETIME=12,YEAR=13,NEWDATE=14,VARCHAR=15,BIT=16,TIMESTAMP2=17,DATETIME2=18,TIME2=19,NEWDECIMAL=246,ENUM=247,SET=248,TINY_BLOB=249,MEDIUM_BLOB=250,LONG_BLOB=251,BLOB=252,VAR_STRING=253,STRING=254,GEOMETRY=255)
    enum='enum enum_field_types {'+','.join('MYSQL_TYPE_'+k+'='+str(v) for k,v in values.items())+'};\n'
    prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
using uchar=unsigned char;using uint=unsigned;using ushort=unsigned short;using ulong=unsigned long;
#define DBUG_ASSERT(x) assert(x)
#define DBUG_ENTER(x) ((void)0)
#define DBUG_RETURN(x) return x
#define PARAMETER_FLAG_UNSIGNED 128
#define MYF(x) x
#define ER_WRONG_ARGUMENTS 1210
static unsigned last_error;
void my_error(unsigned code,unsigned,const char*){last_error=code;}
unsigned uint2korr(const uchar*p){return p[0]|unsigned(p[1])<<8;}
struct String {};
struct THD {bool mariamem_native_wire=true;};
struct Handler {enum_field_types type;enum_field_types field_type()const{return type;}bool is_param_long_data_type()const{return type==MYSQL_TYPE_BLOB;}};
struct Item_param {
 Handler handler;bool streamed=false,no_value=true,null_value=false;unsigned indicator=0;
 bool limit_clause_param=false;
 const Handler* type_handler()const{return &handler;}
 bool has_long_data_value()const{return streamed;}bool has_no_value()const{return no_value;}
 void set_null(){null_value=true;no_value=false;}
 void set_param_func(uchar**pos,ulong len){
  switch(handler.type){case MYSQL_TYPE_BIT:case MYSQL_TYPE_GEOMETRY:case MYSQL_TYPE_INT24:case MYSQL_TYPE_YEAR:set_null();return;default:break;}
  if(len<1||ulong((*pos)[0])+1>len)return;
  *pos+=1+(*pos)[0];no_value=false;
 }
 bool convert_str_value(THD*){return false;}void sync_clones(){}
 bool has_int_value()const{return false;}long long val_int()const{return 0;}bool set_limit_clause_param(long long){return false;}
};
struct Prepared_statement {THD*thd;uint param_count;Item_param**param_array;const char*query(){return "";}uint query_length(){return 0;}};
struct Copy_query_with_rewrite {Copy_query_with_rewrite(THD*,const char*,uint,String*){}bool append(Item_param*){return false;}bool finalize(){return false;}};
bool is_param_null(uchar*p,uint i){return p[i/8]&(1U<<(i%8));}
#define STMT_INDICATOR_NONE 0
'''
    tests=r'''
int main(){
 THD thd;Item_param p{{MYSQL_TYPE_VAR_STRING}};Item_param*items[]={&p};Prepared_statement stmt{&thd,1,items};
 uchar good[]={0,1,253,0,1,'x'},badflag[]={0,1,252,1},badtype[]={0,1,20,0},shorttypes[]={0,1,252},reuse[]={0,0};
 assert(!stmt_execute_packet_sanity_check(&stmt,good,good+sizeof good,false,false,false));
 assert(stmt_execute_packet_sanity_check(&stmt,badflag,badflag+sizeof badflag,false,false,false));
 assert(stmt_execute_packet_sanity_check(&stmt,badtype,badtype+sizeof badtype,false,false,false));
 assert(stmt_execute_packet_sanity_check(&stmt,shorttypes,shorttypes+sizeof shorttypes,false,false,false));
 assert(!stmt_execute_packet_sanity_check(&stmt,reuse,reuse+sizeof reuse,false,false,false));
 Item_param q{{MYSQL_TYPE_BLOB}};q.streamed=true;Item_param*two[]={&p,&q};stmt.param_count=2;stmt.param_array=two;
 uchar secondbad[]={0,1,253,0,252,1};
 assert(stmt_execute_packet_sanity_check(&stmt,secondbad,secondbad+sizeof secondbad,false,false,false));
 assert(q.streamed&&p.handler.type==MYSQL_TYPE_VAR_STRING);
 stmt.param_count=1;stmt.param_array=items;
 using Insert=bool(*)(Prepared_statement*,uchar*,uchar*,uchar*,String*);
 Insert inserters[]={insert_params,insert_params_with_log};
 for(Insert insert:inserters){
  enum_field_types types[]={MYSQL_TYPE_BIT,MYSQL_TYPE_GEOMETRY,MYSQL_TYPE_INT24,MYSQL_TYPE_YEAR};
  for(auto type:types){
   p=Item_param{{type}};uchar nulls[]={0},body[]={1,'x',99};String expanded;
   assert(mariamem_wire_null_fallback(&p));
   assert(!insert(&stmt,nulls,body,body+sizeof body,&expanded));assert(p.null_value);
  }
  p=Item_param{{MYSQL_TYPE_BIT}};uchar marked_null[]={1},surplus[]={1,'x'};String empty;
  assert(insert(&stmt,marked_null,surplus,surplus+sizeof surplus,&empty)); // bitmap NULL never visited the fallback reader
  p=Item_param{{MYSQL_TYPE_VAR_STRING}};uchar nulls[]={0},body[]={1,'x',99};String expanded;
  assert(!mariamem_wire_null_fallback(&p));
  assert(insert(&stmt,nulls,body,body+sizeof body,&expanded)); // ordinary surplus remains rejected
  p=Item_param{{MYSQL_TYPE_VAR_STRING}};
  assert(!insert(&stmt,nulls,body,body+2,&expanded));
  p=Item_param{{MYSQL_TYPE_LONG}};p.streamed=true;last_error=0;
  assert(insert(&stmt,nulls,body,body,&expanded));assert(last_error==1210);
 }
 puts("PASS actual prepared seams:descriptor preflight,NULL fallback,strict surplus,LONG_DATA1210;logged/nonlogged");
}
'''
    cpp=a.output/'seams.cc';cpp.write_text(enum+prelude+'\n'.join(actual.values())+tests)
    binary=a.output/'seams';subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(cpp),'-o',str(binary)],check=True)
    run=subprocess.check_output([str(binary)],text=True);print(run,end='')
    (a.output/'result.json').write_text(json.dumps({'result':'PASS actual source seams;not engine/runtime qualification','source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'function_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in actual.items()},'output':run},indent=2)+'\n')
if __name__=='__main__':main()
