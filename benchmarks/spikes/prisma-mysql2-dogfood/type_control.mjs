import assert from 'node:assert/strict';
import mysql from 'mysql2/promise';
const config={host:process.env.DB_HOST,port:Number(process.env.DB_PORT),user:process.env.DB_USER,password:process.env.DB_PASSWORD,database:process.env.DB_NAME};
const observed={};
for(const safe of [false,true]) {
 const c=await mysql.createConnection({...config,...(safe?{supportBigNumbers:true,bigNumberStrings:true,timezone:'Z'}:{})});
 try {
  const [rows]=await c.query('SELECT `big`,`at`,`blob` FROM Post WHERE id=1');const row=rows[0];
  observed[safe?'safe_options':'default_options']={bigint:String(row.big),bigint_js_type:typeof row.big,datetime:row.at.toISOString(),blob_hex:row.blob.toString('hex'),blob_is_buffer:Buffer.isBuffer(row.blob)};
  assert.equal(row.blob.toString('hex'),'0001007f80ff');
  if(safe) {assert.equal(String(row.big),'9007199254740993');assert.equal(row.at.toISOString(),'2026-03-04T05:06:07.123Z');}
 } finally {await c.end();}
}
const {mapRow}=await import(new URL('./src/conversion.js',import.meta.resolve('@jsr/netscript__prisma-adapter-mysql')));
const converted=mapRow({blob:Buffer.from([0,1,0,127,128,255])},[{name:'blob',fieldType:252}])[0];
assert.equal(typeof converted,'string');assert.equal(converted,'AAEAf4D/');
observed.adapter_conversion={input:'Buffer/Uint8Array',output_type:typeof converted,output:converted};
console.log(JSON.stringify(observed));
