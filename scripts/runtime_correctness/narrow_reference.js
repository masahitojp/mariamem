// Independent native-Wasm oracle. Golden values are produced by the engine,
// not by repeating the Go adapter's arithmetic.
const fs = require("fs"), crypto = require("crypto");
const moduleBytes = fs.readFileSync(process.argv[2]);
const mod = new WebAssembly.Module(moduleBytes);
const cases = JSON.parse(fs.readFileSync(process.argv[3]));
const hash = b => crypto.createHash("sha256").update(b).digest("hex");
const results = [];
for (const c of cases) {
  const x = new WebAssembly.Instance(mod).exports;
  const b = new Uint8Array(x.memory.buffer);
  b.fill(0x57,60,80);
  const width = c.bits/8, valid = c.addr>=0 && c.addr+width<=65536;
  let initial = BigInt("0x"+c.initial);
  if(valid)for(let i=0;i<width;i++)b[c.addr+i]=Number((initial>>BigInt(8*i))&255n);
  const before = hash(b);
  const values = c.args.map(v=>c.result===32?Number(BigInt.asIntN(32,BigInt("0x"+v))):BigInt.asIntN(64,BigInt("0x"+v)));
  let trapped=false,old=0n;
  try{
    const value=x[c.name](c.addr,...values);
    if(value!==undefined)old=BigInt.asUintN(c.result,BigInt(value));
  }catch(e){if(!(e instanceof WebAssembly.RuntimeError))throw e;trapped=true;}
  results.push({...c,before,after:hash(b),trap:trapped,old:old.toString(16)});
}
process.stdout.write(JSON.stringify(results)+"\n");
