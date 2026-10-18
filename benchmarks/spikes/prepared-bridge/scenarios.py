"""Bounded experimental consumer and raw-wire oracles. No fallback drivers."""
import argparse,io,json,struct
import mysql.connector
import pymysql

def prepared_cases(port,pure,no_multi_statements=False):
    flags = dict(client_flags=[-65536]) if no_multi_statements else {}
    c=mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,autocommit=False,**flags)
    text=c.cursor();text.execute('DROP TABLE IF EXISTS prepared_items');text.execute('CREATE TABLE prepared_items(id BIGINT PRIMARY KEY, value VARBINARY(100)) ENGINE=InnoDB');c.commit()
    q=c.cursor(prepared=True)
    q.execute('SELECT ?, ?, ?',(-7,'hello',None));row=q.fetchone();assert row==(-7,'hello',None),row
    q.execute('SELECT ?, ?, ?',(9223372036854775807,'second',None));row=q.fetchone();assert row==(9223372036854775807,'second',None),row
    q.execute('INSERT INTO prepared_items VALUES(?, ?)',(1,b'a\0b'));assert q.rowcount==1;c.rollback()
    q.execute('SELECT COUNT(*) FROM prepared_items');assert q.fetchone()==(0,)
    q.execute('INSERT INTO prepared_items VALUES(?, ?)',(2,b'committed'));c.commit()
    q.execute('SELECT value FROM prepared_items WHERE id=?',(2,));assert bytes(q.fetchone()[0])==b'committed'
    q.close();q=c.cursor(prepared=True)
    try:q.execute('SELEC broken ?',(1,))
    except mysql.connector.Error as e:assert e.errno==1064,(e.errno,str(e))
    else:raise AssertionError('prepare syntax error was accepted')
    q.close()
    if pure:
        q=c.cursor(prepared=True);q.execute('SELECT ?', (io.BytesIO(b'long\0data'),));assert bytes(q.fetchone()[0])==b'long\0data';q.close()
    text.close();c.close()

def raw_cases(port):
    c=pymysql.connect(host='127.0.0.1',port=port,user='root',database='test')
    def prep(sql):
        c._execute_command(22,sql);h=c._read_packet().get_all_data();assert h[0]==0
        sid=int.from_bytes(h[1:5],'little');nc=int.from_bytes(h[5:7],'little');np=int.from_bytes(h[7:9],'little')
        for n in (np,nc):
            for _ in range(n):c._read_packet()
            if n:assert c._read_packet().is_eof_packet()
        return sid
    sid=prep(b'SELECT CAST(? AS SIGNED)')
    other=pymysql.connect(host='127.0.0.1',port=port,user='root',database='test')
    other._execute_command(26,struct.pack('<I',sid))
    try:other._read_packet()
    except pymysql.MySQLError as e:assert e.args[0]==1243,e
    else:raise AssertionError('cross-session handle accepted')
    other.close()
    # CLOSE has no reply. Send PING without waiting: an unexpected CLOSE reply
    # or the old query read-ahead monitor must not desynchronize/abort this session.
    c._execute_command(25,struct.pack('<I',sid));c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
    c._execute_command(26,struct.pack('<I',sid))
    try:c._read_packet()
    except pymysql.MySQLError as e:assert e.args[0]==1243,e
    else:raise AssertionError('closed handle accepted')
    c.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);p.add_argument('--no-multi-statements',action='store_true');a=p.parse_args()
    records=[]
    def run(port):
        for pure in (True,False):
            try:prepared_cases(port,pure,a.no_multi_statements)
            except Exception as e:records.append(dict(case='python-pure' if pure else 'python-cext',result='FAIL',error=repr(e)));continue
            records.append(dict(case='python-pure' if pure else 'python-cext',result='PASS'))
        raw_cases(port);records.append(dict(case='session-handles-and-no-response-close',result='PASS'))
    try:
        if a.host:
            import mariamem
            with mariamem.start(host_binary=a.host) as db:run(db.connection_info()['port'])
        else:run(a.port)
    finally:
        with open(a.output,'w') as f:json.dump(records,f,indent=2)
    return int(any(x['result']=='FAIL' for x in records))
if __name__=='__main__':raise SystemExit(main())
