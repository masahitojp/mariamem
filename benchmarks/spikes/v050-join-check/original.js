import fs from 'node:fs';
const meta = JSON.parse(fs.readFileSync(process.argv[3]));
const module = new WebAssembly.Module(fs.readFileSync(process.argv[2]));
const limit = meta.imports.find(x=>x.kind===2).memory.Limits;
function trial(waiters, deferReclaim) {
 const memory = new WebAssembly.Memory({initial:Number(limit.Min),maximum:Number(limit.Max),shared:true});
 const imports = {};
 let root, child, map, td, reuse, marker, hookCalled=false, joined=false;
 const view=()=>new DataView(memory.buffer);
 const write=(p,v)=>view().setUint32(p,v,true);
 for(const x of WebAssembly.Module.imports(module)) {
  imports[x.module] ??= {};
  if(x.kind==='memory') imports[x.module][x.name]=memory;
  else if(x.kind==='function') imports[x.module][x.name]=(...args)=>{throw new Error(`unexpected import ${x.module}.${x.name} ${args}`);};
  else throw new Error(`unexpected import kind ${x.kind}`);
 }
 imports.wasi_snapshot_preview1.sched_yield=()=>0;
 imports.wasix_32v1.futex_wake=(addr,out)=>{
  if(addr!==15243132) throw new Error(`unexpected wake address ${addr}`);
  hookCalled=true;
  if(!deferReclaim) {
   const rc=root.exports.auditJoin(td);if(rc!==0)throw new Error(`join=${rc}`);joined=true;
   reuse=root.exports.auditMalloc(262144);if(reuse!==map)throw new Error(`allocation not reused ${map}/${reuse}`);
   new Uint8Array(memory.buffer)[marker]=0xa5;
  }
  new Uint8Array(memory.buffer)[out]=1;
  return 0;
 };
 root=new WebAssembly.Instance(module,imports);child=new WebAssembly.Instance(module,imports);
 root.exports.auditInit();
 root.exports.auditTLS.value=32768;write(32772,33024);write(33024+48,0x3fffffff);
 map=root.exports.auditMalloc(262144);if(map<=0)throw new Error('malloc failed');
 td=map+262144-1024;write(td+28,0);write(td+40,map);write(td+44,262144);
 child.exports.auditStack.value=map+262144-4096;marker=child.exports.auditStack.value-1;
 write(15243132,123);write(15244240,0);write(15244244,waiters);
 child.exports.auditUnlock();
 if(deferReclaim || !waiters){const rc=root.exports.auditJoin(td);if(rc!==0)throw new Error(`join=${rc}`);joined=true;reuse=root.exports.auditMalloc(262144);if(reuse!==map)throw new Error('control allocation not reused');new Uint8Array(memory.buffer)[marker]=0xa5;}
 const observed=new Uint8Array(memory.buffer)[marker];
 return {engine:'original-Wasm/Node',waiters,defer_reclaim:deferReclaim,hook_called:hookCalled,joined,map,reused:reuse,stack_result_address:marker,replacement_canary:observed,lifetime_oracle:observed===0xa5?'PASS':'FAIL',scope:'original function bodies; forced host-import schedule, seeded valid heap allocation and pthread layout; not full SQL guest run'};
}
const rows=[trial(1,false),trial(1,true),trial(0,false)];
console.log(JSON.stringify({node:process.version,checks:rows},null,2));
if(rows[0].lifetime_oracle!=='FAIL'||rows.slice(1).some(x=>x.lifetime_oracle!=='PASS'))process.exitCode=1;
