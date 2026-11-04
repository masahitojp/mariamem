import assert from 'node:assert/strict';
import mysql from 'mysql2/promise';
const config={host:process.env.DB_HOST!,port:Number(process.env.DB_PORT),user:process.env.DB_USER!,password:process.env.DB_PASSWORD!,database:process.env.DB_NAME!,connectTimeout:5000};
const cells:any[]=[];
for(const name of ['query_zero','query_parameter','execute_zero','execute_parameter','bigint_default','bigint_safe','binary']) {
  const cell:any={name};let connection:any;
  try {
    connection=await mysql.createConnection({...config,...(name==='bigint_safe'?{supportBigNumbers:true,bigNumberStrings:true}:{})});
    let rows:any[];
    if(name.startsWith('query'))[rows]=await connection.query(name==='query_zero'?'SELECT 1 AS n':'SELECT ? AS n',name==='query_zero'?[]:[1]);
    else if(name.startsWith('execute'))[rows]=await connection.execute(name==='execute_zero'?'SELECT 1 AS n':'SELECT ? AS n',name==='execute_zero'?[]:[1]);
    else if(name.startsWith('bigint'))[rows]=await connection.query('SELECT CAST(9007199254740993 AS SIGNED) AS n');
    else [rows]=await connection.execute('SELECT ? AS n',[Buffer.from([0,0,255])]);
    cell.observed=typeof rows[0].n==='bigint'?rows[0].n.toString():rows[0].n;
    cell.js_type=typeof rows[0].n;
    if(name.startsWith('bigint'))assert.equal(String(rows[0].n),'9007199254740993');
    else if(name==='binary')assert.equal(Buffer.from(rows[0].n).toString('hex'),'0000ff');
    else assert.equal(String(rows[0].n),'1');
    cell.result='PASS';
  } catch(error:any) {cell.result='FAIL';cell.error=String(error);cell.code=error.code;}
  finally {if(connection)await connection.end();}
  cells.push(cell);
}
console.log(JSON.stringify(cells));
