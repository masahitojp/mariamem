import assert from 'node:assert/strict';
import readline from 'node:readline';
const [ormName,name]=process.argv.slice(2);
const {open}=await import(`./${ormName}.mjs`);
const expected={big:'9007199254740993',at:'2026-03-04T05:06:07.123Z',amount:'12345678901234.123456',meta:{text:'日本語\u0000value',nested:[1,true,null]},blob:Buffer.from([0,1,0,127,128,255])};
const print=x=>console.log(JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v));
let db;
try {
 if(name==='live') {
  print({event:'ready',pid:process.pid});
  for await(const line of readline.createInterface({input:process.stdin})) {
   const {command}=JSON.parse(line);
   if(command==='quit')break;
   if(command==='disconnect'){await db.close();db=undefined;print({event:'disconnected'});continue;}
   db=await open();assert.equal(await db.count(),1);assert.equal((await db.user()).name,'baseline');await db.create({email:'live@test'});assert.equal(await db.count(),2);print({event:'mutated',pid:process.pid});
  }
 } else {
  db=await open();
  switch(name) {
   case 'connect':assert.equal((await db.raw('SELECT 1 AS n'))[0].n,1);break;
   case 'count':assert.equal(await db.count(),1);break;
   case 'find':assert.equal((await db.user()).email,'baseline@test');break;
   case 'create':{const u=await db.create({email:'new@test',name:'new'});assert.ok(u.id>1);assert.equal(await db.count(),2);break;}
   case 'bulk':await db.bulk();assert.equal(await db.count(),3);break;
   case 'nested':{const u=await db.nested();const actual=await db.user(u.id,true);assert.equal(Array.from(actual.posts).length,1);assert.equal(Array.from(actual.posts)[0].title,'nested');break;}
   case 'relation':assert.equal(Array.from((await db.user(1,true)).posts)[0].title,'baseline');break;
   case 'update':await db.update();assert.equal((await db.user()).name,'updated');break;
   case 'upsert':await db.upsert();assert.equal((await db.user()).name,'upserted');assert.equal(await db.count(),1);break;
   case 'delete_cascade':await db.remove();assert.equal(await db.posts(),0);break;
   case 'nullable':{const u=await db.create({email:'null@test',name:null});assert.equal((await db.user(u.id)).name,null);break;}
   case 'transaction_commit':await db.transaction(x=>x.create({email:'commit@test'}));assert.equal(await db.count(),2);break;
   case 'transaction_rollback':await assert.rejects(db.transaction(async x=>{await x.create({email:'rollback@test'});throw Error('rollback sentinel');}),/rollback sentinel/);assert.equal(await db.count(),1);break;
   case 'unique_error':{let error;try{await db.create({email:'baseline@test'});}catch(e){error=e;}assert.ok(error,'duplicate was accepted');assert.ok([1062,'ER_DUP_ENTRY'].includes(error.errno)||error.code==='ER_DUP_ENTRY'||error.driverError?.errno===1062,'expected duplicate-key error: '+error);assert.equal(await db.count(),1);break;}
   case 'bigint':assert.equal(String((await db.post()).big),expected.big);break;
   case 'decimal':assert.equal(String((await db.post()).amount),expected.amount);break;
   case 'datetime':assert.equal((await db.post()).at.toISOString(),expected.at);break;
   case 'json':assert.deepEqual((await db.post()).meta,expected.meta);break;
   case 'binary':assert.deepEqual(Buffer.from((await db.post()).blob),expected.blob);break;
   case 'raw_parameter':assert.equal((await db.raw('SELECT ? AS n',[7]))[0].n,7);break;
   case 'raw_zero_parameter':assert.equal((await db.raw('SELECT 7 AS n'))[0].n,7);break;
   case 'aggregate':{const x=await db.aggregate();assert.equal(Number(x.n),1);assert.equal(String(x.total),expected.amount);break;}
   case 'group_by':{const x=await db.group();assert.equal(x.length,1);assert.equal(Number(x[0].n),1);assert.equal(Number(x[0].author),1);break;}
   case 'schema_create':await db.schemaCreate();await db.create({email:'schema@test'});assert.equal(await db.count(),1);break;
   case 'schema_noop':await db.schemaCreate();{const sql=await db.schemaDiff();assert.equal(sql.trim(),'','unexpected schema drift: '+sql);}break;
   case 'schema_update':await db.schemaCreate();await db.schemaUpdate();{const c=await db.raw("SELECT CHARACTER_MAXIMUM_LENGTH AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User' AND COLUMN_NAME='name'");assert.equal(Number(c[0].n),140);}break;
   default:throw Error('unknown case '+name);
  }
  print({result:'PASS',orm:ormName,case:name});
 }
} catch(e) {print({result:'FAIL',orm:ormName,case:name,error:String(e),stack:e.stack,code:e.code,errno:e.errno,sql:e.sql,driverError:e.driverError&&{code:e.driverError.code,errno:e.driverError.errno,sql:e.driverError.sql}});process.exitCode=1;}
finally {if(db)await db.close();}
