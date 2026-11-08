const fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(process.argv[2],'utf8');const js=html.match(/<script>([\s\S]*)<\/script>/)[1];
const nodes={};const document={querySelector(s){return nodes[s]??=(s==='#zoom'?{checked:false}:{innerHTML:''})}};
new vm.Script(js).runInNewContext({document});
for(const zoom of [false,true]){nodes['#zoom'].checked=zoom;nodes['#zoom'].onchange();const svg=nodes['#charts'].innerHTML;if((svg.match(/<svg /g)||[]).length!==3)throw Error('missing charts');const bars=[...svg.matchAll(/<rect x="([\d.e+-]+)" y="([\d.e+-]+)" width="([\d.e+-]+)"/g)];if(bars.length<200)throw Error('missing spans');for(const b of bars){const x=Number(b[1]),y=Number(b[2]),w=Number(b[3]);if(!Number.isFinite(x+y+w)||x<119||x+w>1102||y<0||y>250)throw Error('invalid bar geometry '+b[0])}}
console.log('HTML JavaScript, three charts, zoom modes and span geometry PASS');
