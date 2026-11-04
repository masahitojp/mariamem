const fs=require('node:fs');
const cypress=require('cypress');
const [spec,output]=process.argv.slice(2);
cypress.run({spec,browser:'electron',headless:true,record:false,config:{baseUrl:process.env.UMAMI_DOGFOOD_BASE_URL||'http://localhost:3000',video:false,retries:0,screenshotsFolder:output+'.screenshots'}}).then(r=>{
 const out={};
 for(const key of ['totalTests','totalPassed','totalFailed','totalPending','totalSkipped','browserName','browserVersion','cypressVersion','failures','message'])if(r[key]!==undefined)out[key]=r[key];
 out.runs=(r.runs||[]).map(x=>({spec:x.spec.relative,stats:x.stats,error:x.error,tests:x.tests.map(t=>({title:t.title,state:t.state,displayError:t.displayError,attempts:t.attempts.map(a=>({state:a.state,error:a.error}))}))}));
 fs.writeFileSync(output,JSON.stringify(out,null,2)+'\n');
 process.exitCode=(r.failures||r.totalFailed||r.totalSkipped||r.totalPending)?1:0;
}).catch(error=>{fs.writeFileSync(output,JSON.stringify({runner_error:String(error)},null,2)+'\n');console.error(error);process.exitCode=1;});
