import assert from 'node:assert/strict';
import { createInterface } from 'node:readline';
import { PrismaClient } from './generated/client.ts';
import { PrismaMariaDb } from '@prisma/adapter-mariadb';

const adapter=new PrismaMariaDb({host:process.env.DB_HOST!,port:Number(process.env.DB_PORT),user:process.env.DB_USER!,password:process.env.DB_PASSWORD!,database:process.env.DB_NAME!,connectionLimit:2,connectTimeout:5000,acquireTimeout:10000,...(process.env.PRISMA_PIPELINING==='off'?{pipelining:false}:{})});
const prisma=new PrismaClient({adapter});
const name=process.argv[2];
const countArgs={where:{id:{gt:0}}};
const types={amount:'12345678901234.123456',big:9007199254740993n,at:new Date('2026-03-04T05:06:07.123Z'),meta:{text:'日本語\u0000value',nested:[1,true,null]},blob:Buffer.from([0,1,0,127,128,255])};
const emit=(value:unknown)=>console.log(JSON.stringify(value,(_,v)=>typeof v==='bigint'?v.toString():v));
async function exercise() {
  switch(name) {
    case 'connect': await prisma.$connect(); break;
    case 'find_unique': assert.equal((await prisma.user.findUniqueOrThrow({where:{id:1}})).name,'baseline');break;
    case 'find_many_unfiltered': assert.equal((await prisma.user.findMany()).length,1);break;
    case 'count_unfiltered': assert.equal(await prisma.user.count(),1);break;
    case 'count_filtered': assert.equal(await prisma.user.count(countArgs),1);break;
    case 'create': assert.equal((await prisma.user.create({data:{email:'created@test',name:'new'}})).name,'new');break;
    case 'nested_create': assert.equal((await prisma.user.create({data:{email:'nested@test',posts:{create:{title:'new',...types}}},include:{posts:true}})).posts.length,1);break;
    case 'create_many': assert.equal((await prisma.user.createMany({data:[{email:'a@test'},{email:'b@test'}]})).count,2);break;
    case 'update': assert.equal((await prisma.user.update({where:{id:1},data:{name:'updated'}})).name,'updated');break;
    case 'delete_cascade': await prisma.user.delete({where:{id:1}});assert.equal(await prisma.post.count(countArgs),0);break;
    case 'upsert': assert.equal((await prisma.user.upsert({where:{email:'baseline@test'},update:{name:'upserted'},create:{email:'baseline@test'}})).name,'upserted');break;
    case 'relation': assert.equal((await prisma.user.findUniqueOrThrow({where:{id:1},include:{posts:true}})).posts.length,1);break;
    case 'nullable': assert.equal((await prisma.user.update({where:{id:1},data:{name:null}})).name,null);break;
    case 'transaction_commit': await prisma.$transaction(async tx=>{await tx.user.create({data:{email:'tx@test'}});});assert.equal(await prisma.user.count({where:{email:'tx@test'}}),1);break;
    case 'transaction_rollback': await assert.rejects(prisma.$transaction(async tx=>{await tx.user.create({data:{email:'tx@test'}});throw Error('EXPECTED_ROLLBACK');}),/EXPECTED_ROLLBACK/);assert.equal(await prisma.user.count({where:{email:'tx@test'}}),0);break;
    case 'transaction_array': assert.equal((await prisma.$transaction([prisma.user.create({data:{email:'array@test'}}),prisma.user.update({where:{id:1},data:{name:'array'}})])).length,2);break;
    case 'aggregate': assert.equal((await prisma.user.aggregate({_sum:{id:true}}))._sum.id,1);break;
    case 'group_by': assert.equal((await prisma.user.groupBy({by:['name'],_count:{_all:true}}))[0]._count._all,1);break;
    case 'raw_parameter': assert.equal(String((await prisma.$queryRaw<any[]>`SELECT ${1} AS n`)[0].n),'1');break;
    case 'raw_zero_parameter': assert.equal(String((await prisma.$queryRawUnsafe<any[]>('SELECT 1 AS n'))[0].n),'1');break;
    case 'execute_raw': assert.equal(await prisma.$executeRaw`UPDATE User SET name=${'raw'} WHERE id=${1}`,1);break;
    case 'unique_error': await assert.rejects(prisma.user.create({data:{email:'baseline@test'}}),(error:any)=>error.code==='P2002');assert.equal((await prisma.user.findUniqueOrThrow({where:{id:1}})).name,'baseline');break;
    case 'decimal': assert.equal((await prisma.post.findUniqueOrThrow({where:{id:1},select:{amount:true}})).amount.toFixed(6),types.amount);break;
    case 'bigint': assert.equal((await prisma.post.findUniqueOrThrow({where:{id:1},select:{big:true}})).big,types.big);break;
    case 'datetime': assert.equal((await prisma.post.findUniqueOrThrow({where:{id:1},select:{at:true}})).at.toISOString(),types.at.toISOString());break;
    case 'json': assert.deepEqual((await prisma.post.findUniqueOrThrow({where:{id:1},select:{meta:true}})).meta,types.meta);break;
    case 'binary': assert.deepEqual(Buffer.from((await prisma.post.findUniqueOrThrow({where:{id:1},select:{blob:true}})).blob),types.blob);break;
    default: throw Error('Unknown case '+name);
  }
}
try {
  if(name==='live') {
    emit({event:'ready',pid:process.pid});
    const lines=createInterface({input:process.stdin});
    for await(const line of lines) {
      const command=JSON.parse(line).command;
      if(command==='read-mutate') {
        const user=await prisma.user.findUniqueOrThrow({where:{id:1}});
        assert.equal(user.name,'baseline');
        await prisma.user.update({where:{id:1},data:{name:'mutated'}});
        emit({result:'PASS',pid:process.pid,baseline_seen:true});
      } else if(command==='disconnect') {await prisma.$disconnect();emit({result:'PASS',pid:process.pid,disconnected:true});}
      else if(command==='quit') break;
      else throw Error('Unknown live command');
    }
  } else {await exercise();emit({result:'PASS',case:name});}
} catch(error:any) {
  emit({result:'FAIL',case:name,error:String(error),code:error.code,meta:error.meta});
  process.exitCode=1;
} finally {await prisma.$disconnect();}
