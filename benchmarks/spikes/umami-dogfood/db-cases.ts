// Bundle in the disposable upstream project with its original tsconfig and packages.
import assert from 'node:assert/strict';
import prisma from './src/lib/prisma';
import {createWebsite,getWebsite,getAllWebsites,updateWebsite,resetWebsite,deleteWebsite} from './src/queries/prisma/website';
import {createSession} from './src/queries/sql/sessions/createSession';
import {saveEvent} from './src/queries/sql/events/saveEvent';
import {getWebsiteStats} from './src/queries/sql/getWebsiteStats';
import {getPageviewStats} from './src/queries/sql/pageviews/getPageviewStats';
import {getEventStats} from './src/queries/sql/events/getEventStats';
const rows:any[]=[];
async function cell(name:string,f:()=>Promise<unknown>){try{await f();rows.push({name,result:'PASS'});}catch(e:any){rows.push({name,result:'FAIL',code:e.code,error:String(e)});}console.log(JSON.stringify(rows.at(-1)));}
async function main(){
 const websiteId='11111111-1111-4111-8111-111111111111',owner='41e2b680-648e-4b09-bcd7-3e2b10c06264';
 const s1='22222222-2222-4222-8222-222222222222',s2='33333333-3333-4333-8333-333333333333';
 const v1='44444444-4444-4444-8444-444444444444',v2='55555555-5555-4555-8555-555555555555';
 const filters:any={startDate:new Date('2026-01-01T00:00:00Z'),endDate:new Date('2026-01-03T23:59:59Z'),unit:'day',timezone:'UTC'};
 try{
  await cell('migration-admin-seed',async()=>{const u=await prisma.client.user.findUniqueOrThrow({where:{id:owner}});assert.equal(u.username,'admin');assert.equal(u.role,'admin');});
  await cell('upstream-create-and-read-website',async()=>{await createWebsite({id:websiteId,name:'mariamem analytics',domain:'example.test',userId:owner,createdBy:owner});assert.equal((await getWebsite(websiteId)).name,'mariamem analytics');});
  await cell('upstream-save-session-and-events',async()=>{
   await createSession({id:s1,websiteId,browser:'firefox',country:'JP'} as any);await createSession({id:s2,websiteId,browser:'chrome',country:'US'} as any);
   for(const [sessionId,visitId,createdAt,urlPath] of [[s1,v1,'2026-01-01T00:00:00Z','/日本語'],[s1,v1,'2026-01-01T00:01:00Z','/pricing'],[s2,v2,'2026-01-01T23:30:00Z','/home']])await saveEvent({websiteId,sessionId,visitId,createdAt:new Date(createdAt),urlPath});
   await saveEvent({websiteId,sessionId:s1,visitId:v1,createdAt:new Date('2026-01-01T00:01:00Z'),urlPath:'/signup',eventName:'signup',eventData:{plan:'pro',quantity:2}});
   assert.equal(await prisma.client.websiteEvent.count({where:{websiteId}}),4);
  });
  await cell('upstream-visitor-bounce-duration-stats',async()=>{const [r]=await getWebsiteStats(websiteId,filters);assert.deepEqual([r.pageviews,r.visitors,r.visits,r.bounces,r.totaltime].map(Number),[3,2,2,1,60]);});
  await cell('upstream-country-filter-join',async()=>{const [r]=await getWebsiteStats(websiteId,{...filters,country:'JP'});assert.deepEqual([r.pageviews,r.visitors,r.visits,r.bounces,r.totaltime].map(Number),[2,1,1,0,60]);});
  await cell('upstream-daily-UTC',async()=>{const r:any[]=await getPageviewStats(websiteId,filters);assert.deepEqual(r.map(x=>[x.x,Number(x.y)]),[['2026-01-01 00:00:00',3]]);});
  await cell('upstream-daily-Tokyo',async()=>{const r:any[]=await getPageviewStats(websiteId,{...filters,timezone:'Asia/Tokyo'});assert.deepEqual(r.map(x=>[x.x,Number(x.y)]),[['2026-01-01 00:00:00',2],['2026-01-02 00:00:00',1]]);});
  await cell('upstream-custom-event-and-properties',async()=>{const r:any[]=await getEventStats(websiteId,filters);assert.equal(r.length,1);assert.equal(r[0].x,'signup');assert.equal(Number(r[0].y),1);assert.equal(await prisma.client.eventData.count({where:{websiteId}}),2);});
  await cell('upstream-user-website-relation',async()=>{assert((await getAllWebsites(owner)).some(w=>w.id===websiteId));});
  await cell('upstream-update-website',async()=>{await updateWebsite(websiteId,{name:'updated'});assert.equal((await getWebsite(websiteId)).name,'updated');});
  await cell('upstream-reset-transaction',async()=>{await resetWebsite(websiteId);assert.equal(await prisma.client.websiteEvent.count({where:{websiteId}}),0);assert.equal(await prisma.client.session.count({where:{websiteId}}),0);assert.equal(await prisma.client.eventData.count({where:{websiteId}}),0);assert((await getWebsite(websiteId)).resetAt);});
  await cell('upstream-delete-website',async()=>{await deleteWebsite(websiteId);assert.equal(await getWebsite(websiteId),null);});
 }finally{await prisma.client.$disconnect();}
 console.log(JSON.stringify({summary:{PASS:rows.filter(x=>x.result==='PASS').length,FAIL:rows.filter(x=>x.result==='FAIL').length},cells:rows}));if(rows.some(x=>x.result==='FAIL'))process.exitCode=1;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
