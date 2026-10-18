"""Pin the native reference and record actual PREPARE descriptors, without execute."""
import argparse,json
import pymysql
from pymysql.protocol import FieldDescriptorPacket

p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args()
c=pymysql.connect(host='127.0.0.1',port=a.port,user='root',database='test',charset='utf8mb4')
with c.cursor() as q:
    q.execute('SELECT VERSION()');version=q.fetchone()[0]
assert version.startswith('12.3.3-'),version
cases=[]
for sql in ['SELECT ?, ?, ?', 'SELECT CAST(? AS SIGNED), CAST(? AS CHAR)', 'SELECT 1 WHERE ? IS NULL']:
    c._execute_command(22,sql.encode())
    h=c._read_packet().get_all_data();assert h[0]==0
    sid=int.from_bytes(h[1:5],'little');nc=int.from_bytes(h[5:7],'little');np=int.from_bytes(h[7:9],'little')
    params=[];columns=[]
    for count,values in [(np,params),(nc,columns)]:
        for _ in range(count):
            raw=c._read_packet().get_all_data();f=FieldDescriptorPacket(raw,'utf8')
            values.append(dict(name=f.name,table=f.table_name,type=f.type_code,charset=f.charsetnr,flags=f.flags,length=f.length,decimals=f.scale,raw=raw.hex()))
        if count: assert c._read_packet().is_eof_packet()
    cases.append(dict(sql=sql,params=params,columns=columns))
    c._execute_command(25,sid.to_bytes(4,'little'))
c.close()
with open(a.output,'w') as out:json.dump(dict(version=version,cases=cases),out,indent=2)
print(json.dumps(dict(version=version,cases=cases),indent=2))
