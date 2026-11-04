import assert from 'node:assert/strict';
import { createInterface } from 'node:readline';
import { PrismaClient } from './generated/client.ts';
import { PrismaMariaDb } from '@prisma/adapter-mariadb';

const compatibility = process.env.PRISMA_PIPELINING==='off' ? {pipelining:false} : {};
const adapter = new PrismaMariaDb({...compatibility,host:process.env.DB_HOST!,port:Number(process.env.DB_PORT),user:process.env.DB_USER!,password:process.env.DB_PASSWORD!,database:process.env.DB_NAME!,connectionLimit:2,connectTimeout:5000,acquireTimeout:10000});
const prisma = new PrismaClient({adapter});
const types = {amount:'12345678901234.123456',big:9007199254740993n,at:new Date('2026-03-04T05:06:07.123Z'),meta:{text:'日本語\u0000value',nested:[1,true,null]},blob:Buffer.from([0,1,0,127,128,255])};
const emit = (value: unknown) => console.log(JSON.stringify(value));
async function driverProbe() {
  const mariadb=await import('mariadb');
  const connection=await mariadb.createConnection({host:process.env.DB_HOST!,port:Number(process.env.DB_PORT),user:process.env.DB_USER!,password:process.env.DB_PASSWORD!,database:process.env.DB_NAME!,pipelining:false,prepareCacheLength:0});
  try {
    assert.equal((await connection.query('SELECT 1 AS n'))[0].n,1);
    assert.equal((await connection.execute('SELECT ? AS n',[1]))[0].n,1);
    let zeroError:any;
    try {await connection.execute('SELECT 1 AS n');} catch(error) {zeroError=error;}
    assert.equal(zeroError?.errno,1835,'current zero-parameter prepared failure must reproduce');
    assert.equal((await connection.query('SELECT 1 AS n'))[0].n,1);
    return {result:'REPRODUCED_ZERO_PARAMETER_EXECUTE_FAILURE',text_query:true,parameterized_execute:true,zero_parameter_errno:zeroError.errno,healthy_after_error:true};
  } finally {await connection.end();}
}
async function seed() {
  const user=await prisma.user.create({data:{email:'baseline@example.test',name:'baseline',posts:{create:{title:'baseline',...types}}},include:{posts:true}});
  assert.equal(user.posts.length,1);
  return {result:'PASS',stage:'seed',userId:user.id};
}
async function exercise() {
  const countArgs=process.env.PRISMA_PARAMETERIZED_COUNTS==='1' ? {where:{id:{gt:0}}} : undefined;
  assert.equal(await prisma.user.count(countArgs),1,'baseline must be restored');
  assert.equal(await prisma.post.count(countArgs),1);
  const baseline=await prisma.user.findUniqueOrThrow({where:{email:'baseline@example.test'},include:{posts:true}});
  const post=baseline.posts[0];
  assert.equal(post.amount.toFixed(6),types.amount);
  assert.equal(post.big,types.big);
  assert.equal(post.at.toISOString(),types.at.toISOString());
  assert.deepEqual(post.meta,types.meta);
  assert.deepEqual(Buffer.from(post.blob),types.blob);
  const created=await prisma.user.create({data:{email:'mutable@example.test',name:'first',posts:{create:{title:'created',...types}}},include:{posts:true}});
  assert.equal(created.posts.length,1);
  const updated=await prisma.user.update({where:{id:created.id},data:{name:'updated'}});
  assert.equal(updated.name,'updated');
  await prisma.user.delete({where:{id:created.id}});
  assert.equal(await prisma.post.count(countArgs),1,'cascade must remove related row');
  await assert.rejects(prisma.$transaction(async tx=>{
    await tx.user.create({data:{email:'rollback@example.test'}});
    throw new Error('DOGFOOD_ROLLBACK');
  }),/DOGFOOD_ROLLBACK/);
  assert.equal(await prisma.user.count({where:{email:'rollback@example.test'}}),0);
  await prisma.$transaction(async tx=>{
    await tx.user.create({data:{email:'committed@example.test'}});
  });
  assert.equal(await prisma.user.count(countArgs),2);
  return {result:'PASS',stage:'case',pid:process.pid,crud:true,relations:true,cascade:true,rollback:true,commit:true,types:{decimal:post.amount.toFixed(6),bigint:post.big.toString(),datetime:post.at.toISOString(),json:post.meta,blobHex:Buffer.from(post.blob).toString('hex')}};
}
try {
  if (process.argv[2]==='driver') emit(await driverProbe());
  else if (process.argv[2]==='seed') emit(await seed());
  else {
    emit({event:'ready',pid:process.pid});
    const lines=createInterface({input:process.stdin});
    for await (const line of lines) {
      const {command}=JSON.parse(line);
      if(command==='case')emit(await exercise());
      else if(command==='disconnect') {await prisma.$disconnect();emit({result:'PASS',stage:'disconnect',pid:process.pid});}
      else if(command==='quit')break;
      else throw new Error('unknown command');
    }
  }
} catch(error) {
  emit({result:'FAIL',error:String(error),stack:error instanceof Error?error.stack:undefined});
  process.exitCode=1;
} finally {
  await prisma.$disconnect();
}
