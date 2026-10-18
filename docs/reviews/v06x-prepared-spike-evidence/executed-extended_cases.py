"""Additional cases kept outside the clean build source until guest completion."""
import argparse,importlib.util,json,sys,struct
from pathlib import Path
import mysql.connector,pymysql

def cases(port):
    out=[]
    def record(name,fn):
        try:detail=fn();out.append(dict(case=name,result='PASS',detail=detail))
        except Exception as e:out.append(dict(case=name,result='FAIL',error=repr(e)))
    for pure in (True,False):
        def execute_values(pure=pure):
            c=mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,autocommit=True,connection_timeout=10,read_timeout=20)
            try:
                q=c.cursor(prepared=True)
                rows=[]
                for values in [(-7,'hello',None),(9223372036854775807,'second',None),(0,'日本語',None)]:
                    q.execute('SELECT ?, ?, ?',values);rows.append(q.fetchone());assert rows[-1]==values,rows[-1]
                q.close();return dict(rows=rows)
            finally:c.close()
        record('typed-values-pure' if pure else 'typed-values-cext',execute_values)
        def syntax(pure=pure):
            c=mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,autocommit=True,connection_timeout=10,read_timeout=20)
            try:
                q=c.cursor(prepared=True)
                try:q.execute('SELEC broken ?',(1,))
                except mysql.connector.Error as e:
                    original=dict(errno=e.errno,sqlstate=e.sqlstate,message=str(e));assert e.errno==1064,original
                else:raise AssertionError('missing syntax error')
                q.close();return original
            finally:c.close()
        record('prepare-error-pure' if pure else 'prepare-error-cext',syntax)
    c=pymysql.connect(host='127.0.0.1',port=port,user='root',database='test',read_timeout=20)
    def prep(sql):
        c._execute_command(22,sql.encode());h=c._read_packet().get_all_data();assert h[0]==0
        sid=int.from_bytes(h[1:5],'little');np=int.from_bytes(h[7:9],'little');nc=int.from_bytes(h[5:7],'little')
        for count in (np,nc):
            for _ in range(count):c._read_packet()
            if count:assert c._read_packet().is_eof_packet()
        return sid
    def value_no_types():
        sid=prep('SELECT CAST(? AS SIGNED)')
        values=[]
        for fresh,n in [(True,-17),(False,91)]:
            payload=struct.pack('<IBI',sid,0,1)+b'\0'+bytes([fresh])+(b'\x08\0' if fresh else b'')+struct.pack('<q',n)
            c._execute_command(23,payload)
            assert c._read_packet().get_all_data()==b'\x01'
            c._read_packet();assert c._read_packet().is_eof_packet()
            row=c._read_packet().get_all_data();assert row[:2]==b'\0\0';assert len(row)==10,row.hex()
            values.append(struct.unpack('<q',row[2:])[0]);assert values[-1]==n
            assert c._read_packet().is_eof_packet()
        c._execute_command(25,struct.pack('<I',sid));return values
    record('execute-type-descriptor-reuse',value_no_types)
    def longdata():
        sid=prep('SELECT ?')
        for chunk in (b'part\0',b'two'):
            c._execute_command(24,struct.pack('<IH',sid,0)+chunk)
        c._execute_command(23,struct.pack('<IBI',sid,0,1)+b'\0\1\xfc\0')
        assert c._read_packet().get_all_data()==b'\x01'
        c._read_packet();assert c._read_packet().is_eof_packet()
        row=c._read_packet().get_all_data();assert row==b'\0\0\x08part\0two',row.hex();assert c._read_packet().is_eof_packet()
        c._execute_command(25,struct.pack('<I',sid));return row.hex()
    record('long-data-chunks-no-response-then-execute',longdata)
    c.close()
    return out

p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);a=p.parse_args()
if a.host:
 import mariamem
 with mariamem.start(host_binary=a.host) as db:results=cases(db.connection_info()['port'])
else:results=cases(a.port)
Path(a.output).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
sys.exit(any(x['result']=='FAIL' for x in results))
