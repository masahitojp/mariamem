'use strict';
// Only coordination/oracles are JS; all target data accesses and locks are Wasm.
const { Worker, isMainThread, parentPort, workerData } = require('node:worker_threads');
const fs = require('node:fs');
const HEAD=24020976,LATCH=24020736,END=24020864,SCRATCH=256;
const VA=0x1111111111111111n,VB=0x2222222222222222n;
function wordOK(x,a,b){for(let i=0n;i<64n;i+=8n){const v=(x>>i)&255n;if(v!==((a>>i)&255n)&&v!==((b>>i)&255n))return false;}return true;}
function record(c,kind,mode,a,b){
 c.reads++;
 if(kind==='head'){
   const full=(a===100n&&b===900n)||(a===101n&&b===0n);
   if(!full){c.hybrid++;if(c.samples.length<4)c.samples.push([String(a),String(b)]);}
   if(a>101n||(a===101n&&b>0n))c.ahead++;
   if(!wordOK(a,100n,101n)||!wordOK(b,900n,0n)||(mode!=='distinct'&&!full))c.forbidden++;
 }else if(!wordOK(a,VA,VB)||(mode!=='distinct'&&a!==VA&&a!==VB))c.forbidden++;
}
async function run(){
 const [file,kind,mode,nText]=process.argv.slice(2),n=Number(nText);
 const module=new WebAssembly.Module(fs.readFileSync(file));
 const memory=new WebAssembly.Memory({initial:400,maximum:400,shared:true});
 const init=new WebAssembly.Instance(module,{env:{memory}}).exports;
 const dv=new DataView(memory.buffer);dv.setBigUint64(512,100n,true);dv.setBigUint64(520,900n,true);dv.setBigUint64(528,101n,true);dv.setBigUint64(536,0n,true);
 init.copy_head(512);init.write_view(VA);
 const ctrl=new SharedArrayBuffer(16),cs=new Int32Array(ctrl);
 const promise=role=>new Promise((resolve,reject)=>{
   const w=new Worker(__filename,{workerData:{module,memory,ctrl,role,kind,mode,n}});let result;
   w.on('message',m=>{result=m;});w.on('error',reject);w.on('exit',code=>code?reject(new Error('worker exit '+code)):resolve(result));
 });
 const pw=promise('writer'),pr=promise('reader');
 while(Atomics.load(cs,0)!==2){const v=Atomics.load(cs,0);if(v!==2)Atomics.wait(cs,0,v,1000);}
 Atomics.store(cs,1,1);Atomics.notify(cs,1,2);
 const [_,counts]=await Promise.all([pw,pr]);
 console.log(JSON.stringify({engine:'Node/Wasm',kind,mode,backing:'shared WebAssembly.Memory',iterations:n,counts}));
 if(counts.forbidden)process.exitCode=2;
}
function worker(){
 const {module,memory,ctrl,role,kind,mode,n}=workerData,e=new WebAssembly.Instance(module,{env:{memory}}).exports,cs=new Int32Array(ctrl);
 let wr=kind==='head'?END:LATCH,rd=kind==='head'?LATCH:SCRATCH;if(mode==='shared')rd=wr;
 const counts={reads:0,hybrid:0,ahead:0,forbidden:0,samples:[]};
 Atomics.add(cs,0,1);Atomics.notify(cs,0);while(Atomics.load(cs,1)===0)Atomics.wait(cs,1,0);
 for(let i=0;i<n;i++){
   if(mode==='ordered'){
     const want=role==='writer'?i*2:i*2+1;
     while(Atomics.load(cs,2)!==want){const old=Atomics.load(cs,2);if(old!==want)Atomics.wait(cs,2,old,1000);}
   }
   if(role==='writer'){
     e.lock(wr);if(kind==='head')e.copy_head(512+(i%2)*16);else e.write_view(i%2?VB:VA);e.unlock(wr);
   }else{
     e.lock(rd);const [a,b]=kind==='head'?e.read_head():[e.read_view(),0n];record(counts,kind,mode,a,b);e.unlock(rd);
     if(mode==='ordered'&&(kind==='head'?(a!==BigInt(100+i%2)||b!==BigInt(900*(1-i%2))):(a!==(i%2?VB:VA))))throw new Error('ordered stale result');
   }
   if(mode==='ordered'){Atomics.add(cs,2,1);Atomics.notify(cs,2);}
 }
 parentPort.postMessage(counts);
}
if(isMainThread)run().catch(e=>{console.error(e);process.exit(1);});else worker();
