const fs=require('node:fs'), crypto=require('node:crypto'), assert=require('node:assert/strict');
const moduleBytes=fs.readFileSync(process.argv[2]);const mod=new WebAssembly.Module(moduleBytes);const cases=JSON.parse(fs.readFileSync(process.argv[3]));
for(const c of cases){
 const x=new WebAssembly.Instance(mod).exports;let mem=new Uint8Array(x.memory.buffer);for(let i=0;i<mem.length;i++)mem[i]=(i*7+3)&255;
 if(c.grow){assert.equal(x.grow(c.grow),1);mem=new Uint8Array(x.memory.buffer);assert.equal(mem[65536],0);assert.equal(mem[65535],(65535*7+3)&255);}
 let before=crypto.createHash('sha256').update(mem).digest('hex'),value='',trap=false,message='';
 try{value=x[c.op](c.addr).toString();}catch(e){assert(e instanceof WebAssembly.RuntimeError);trap=true;message=e.message;}
 assert.equal(trap,c.expected_trap,JSON.stringify(c));const after=crypto.createHash('sha256').update(mem).digest('hex');if(trap)assert.equal(before,after);
 console.log(JSON.stringify({...c,trap,value,message,before,after}));
}
const x=new WebAssembly.Instance(mod).exports;assert.equal(x.grow(0),1);assert.equal(x.grow(1),1);assert.equal(x.grow(1),2);assert.equal(x.grow(1),-1);assert.equal(x.grow(-1),-1);console.error('WASM reference grow/max/failure PASS; host survives all traps');
