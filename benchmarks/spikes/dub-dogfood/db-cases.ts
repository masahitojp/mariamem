// Copy to apps/web/.mariamem-dogfood.ts and run there; upstream modules stay unchanged.
import assert from 'node:assert/strict';
import { prisma } from './lib/prisma';
import { getLinksCount } from './lib/api/links/get-links-count';
const rows:any[]=[];
async function cell(name:string,operation:()=>Promise<unknown>){
 try{await operation();rows.push({name,result:'PASS'});}
 catch(error:any){rows.push({name,result:'FAIL',code:error.code,error:String(error)});}
 console.log(JSON.stringify(rows.at(-1)));
}
async function main() {
const ws='clrei1gld0002vs9mzn93p8ik';
const user='user_cludszk1h0000wmd2e0ea2b0p';
const base:any={workspaceId:ws};
try {
 await cell('upstream-seed-readback',async()=>{
  assert.equal((await prisma.project.findUniqueOrThrow({where:{id:ws}})).slug,'acme');
  assert.equal(await prisma.user.count(),4);
  assert.equal(await prisma.projectUsers.count({where:{projectId:ws}}),4);
  const found=await prisma.user.findUniqueOrThrow({where:{id:user}});
  assert.equal('passwordHash' in found,false); // Upstream client omit is active.
 });
 await cell('fixture-create-with-upstream-client',async()=>{
  await prisma.tag.createMany({data:[{id:'tag_dog_a',name:'dog-a',projectId:ws},{id:'tag_dog_b',name:'dog-b',projectId:ws}]});
  await prisma.link.create({data:{id:'link_dog_a',domain:'dub.sh',key:'dog-a',url:'https://example.test/日本語?a=1',shortLink:'https://dub.sh/dog-a',projectId:ws,userId:user,tenantId:'tenant-a',saleAmount:9007199254740993n,geo:{JP:'https://example.test/jp'},tags:{create:[{tagId:'tag_dog_a'},{tagId:'tag_dog_b'}]}}});
  await prisma.link.createMany({data:[{id:'link_dog_b',domain:'dub.sh',key:'dog-b',url:'https://example.test/b',shortLink:'https://dub.sh/dog-b',projectId:ws,userId:user,tenantId:'tenant-b'},{id:'link_dog_archived',domain:'dub.sh',key:'dog-archive',url:'https://example.test/archived',shortLink:'https://dub.sh/dog-archive',projectId:ws,archived:true}]});
 });
 await cell('upstream-count-default',async()=>assert.equal(await getLinksCount(base),2));
 await cell('upstream-count-archived',async()=>assert.equal(await getLinksCount({...base,showArchived:true}),3));
 await cell('upstream-count-workspace-isolation',async()=>assert.equal(await getLinksCount({workspaceId:'absent'} as any),0));
 await cell('upstream-count-tenant',async()=>assert.equal(await getLinksCount({...base,tenantId:'tenant-a'}),1));
 await cell('upstream-count-search',async()=>assert.equal(await getLinksCount({...base,search:'日本語'}),1));
 await cell('upstream-count-domain',async()=>assert.equal(await getLinksCount({...base,domain:'missing.test'}),0));
 await cell('upstream-count-with-tags',async()=>assert.equal(await getLinksCount({...base,withTags:true}),1));
 await cell('upstream-count-tag-id',async()=>assert.equal(await getLinksCount({...base,tagId:'tag_dog_a'}),1));
 await cell('upstream-count-tag-names',async()=>assert.equal(await getLinksCount({...base,tagNames:['dog-b']}),1));
 await cell('upstream-count-group-domain',async()=>assert.deepEqual(await getLinksCount({...base,groupBy:'domain'}),[{domain:'dub.sh',_count:2}]));
 await cell('upstream-count-group-tags',async()=>{
  const r:any[]=await getLinksCount({...base,groupBy:'tagId'}) as any;
  assert.deepEqual(r.map(x=>[x.tagId,x._count]).sort(),[['tag_dog_a',1],['tag_dog_b',1]]);
 });
 await cell('compound-id-and-relation-read',async()=>{
  const l=await prisma.link.findUniqueOrThrow({where:{domain_key:{domain:'dub.sh',key:'dog-a'}},include:{tags:{include:{tag:true}},user:true,project:true}});
  assert.equal(l.tags.length,2);assert.equal(l.user?.id,user);assert.equal(l.project?.id,ws);
  assert.equal(l.saleAmount,9007199254740993n);assert.deepEqual(l.geo,{JP:'https://example.test/jp'});
 });
 await cell('transaction-rollback',async()=>{
  await assert.rejects(prisma.$transaction(async tx=>{await tx.link.update({where:{id:'link_dog_b'},data:{clicks:99}});throw Error('EXPECTED_ROLLBACK');}),/EXPECTED_ROLLBACK/);
  assert.equal((await prisma.link.findUniqueOrThrow({where:{id:'link_dog_b'}})).clicks,0);
 });
 await cell('unique-error-and-continuation',async()=>{
  await assert.rejects(prisma.tag.create({data:{id:'tag_duplicate',name:'dog-a',projectId:ws}}),(e:any)=>e.code==='P2002');
  assert.equal(await getLinksCount(base),2);
 });
 await cell('upstream-playwright-setup-idempotent',async()=>{
  const {setupTestWorkspace}=await import('./playwright/api/setup-test-workspace');
  const a=await setupTestWorkspace(),b=await setupTestWorkspace();
  assert.equal(a.workspaceId,b.workspaceId);assert.equal(a.userId,b.userId);
 });
 await cell('upstream-list-offset-and-cursor',async()=>{
  const {getLinksForWorkspace}=await import('./lib/api/links/get-links-for-workspace');
  const f:any={...base,pageSize:1,sortBy:'createdAt',searchMode:'fuzzy'};
  const first=await getLinksForWorkspace(f);assert.equal(first.length,1);
  const next=await getLinksForWorkspace({...f,startingAfter:first[0].id});assert.equal(next.length,1);assert.notEqual(next[0].id,first[0].id);
 });
 await cell('relation-mode-prisma-cascade',async()=>{
  await prisma.tag.delete({where:{id:'tag_dog_a'}});
  assert.equal(await prisma.linkTag.count({where:{tagId:'tag_dog_a'}}),0);
  assert.equal(await prisma.link.count({where:{id:'link_dog_a'}}),1);
 });
} finally {await prisma.$disconnect();}
console.log(JSON.stringify({summary:{PASS:rows.filter(x=>x.result==='PASS').length,FAIL:rows.filter(x=>x.result==='FAIL').length},cells:rows}));
if(rows.some(x=>x.result==='FAIL'))process.exitCode=1;

}
main().catch(error=>{console.error(error);process.exitCode=1;});
