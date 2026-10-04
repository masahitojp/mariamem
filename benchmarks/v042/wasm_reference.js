// Minimal shared-memory WASM reference. No product/generated code is patched.
const assert = require('node:assert/strict');
const u=n=>{const b=[];do{let x=n&127;n=Math.floor(n/128);b.push(x|(n?128:0));}while(n);return b;};
const vec=a=>[...u(a.length),...a.flat()];
const str=s=>[...u(s.length),...Buffer.from(s)];
const sec=(id,b)=>[id,...u(b.length),...b];
const types=vec([[0x60,1,0x7f,1,0x7f],[0x60,1,0x7f,1,0x7e],[0x60,0,1,0x7f]]);
const functions=vec([[0],[1],[2],[0]]);
const mem=[1,3,...u(4096),...u(32768)];
const exported=vec([['load32',0,0],['load64off8',0,1],['size',0,2],['grow',0,3],['memory',2,0]].map(([s,k,i])=>[...str(s),k,i]));
const body=bytes=>[...u(bytes.length+1),0,...bytes];
const code=vec([body([0x20,0,0x28,2,0,0x0b]),body([0x20,0,0x29,3,8,0x0b]),body([0x3f,0,0x0b]),body([0x20,0,0x40,0,0x0b])]);
const binary=Uint8Array.from([0,97,115,109,1,0,0,0,...sec(1,types),...sec(3,functions),...sec(5,mem),...sec(7,exported),...sec(10,code)]);
const x=new WebAssembly.Instance(new WebAssembly.Module(binary)).exports;
assert.equal(x.size(),4096);let results=[];
for(const [name,f,addr] of [['initial-oob',x.load32,268435456],['width-crosses-end',x.load32,268435454],['offset-overflow',x.load64off8,4294967288]]){
 let trapped=false;try{f(addr);}catch(e){assert(e instanceof WebAssembly.RuntimeError);trapped=true;results.push({name,trap:e.message});}assert(trapped,name);
}
let bytes=new Uint8Array(x.memory.buffer);bytes[268435455]=91;
assert.equal(x.grow(0),4096);for(const pages of [1,2,3]){const old=x.size();assert.equal(x.grow(pages),old);bytes=new Uint8Array(x.memory.buffer);assert.equal(bytes[old*65536],0);assert.equal(bytes[268435455],91);}
assert.equal(x.grow(32768-x.size()),4102);assert.equal(x.size(),32768);assert.equal(x.grow(1),-1);assert.equal(x.size(),32768);assert.equal(x.grow(-1),-1);
console.log(JSON.stringify({engine:process.version,shared:true,initial_pages:4096,max_pages:32768,results,grow:'PASS'}));
