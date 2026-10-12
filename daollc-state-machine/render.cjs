const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{spawn}=require('child_process');
const scratch='C:/Users/yaelm/AppData/Local/hermes/cache/scratch';
const profile=path.join(scratch,'daollc-browser-'+Date.now());fs.mkdirSync(profile);
const proc=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-allow-origins=http://localhost',...(process.argv.includes('--webmcp')?['--enable-features=WebMCP']:[]),'--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
const wait=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function rpc(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function click(id){await evaluate('document.getElementById('+JSON.stringify(id)+').click()');await wait(30);}
(async()=>{try{
let port;for(let i=0;i<100;i++){const f=path.join(profile,'DevToolsActivePort');if(fs.existsSync(f)){port=fs.readFileSync(f,'utf8').split('\n')[0];break;}await wait(100);}if(!port)throw Error('Chrome CDP startup timeout');
const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(x=>x.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
await rpc('Page.enable');await rpc('Runtime.enable');const target=process.argv.find(a=>a.startsWith('--url='))?.slice(6)||'http://127.0.0.1:4186/';if(new URL(target).hostname!=='127.0.0.1')throw Error('Verification target must be loopback');await rpc('Page.navigate',{url:target});
let ready=false;for(let i=0;i<100;i++){if(await evaluate('!!globalThis.daollcInspection')){ready=true;break;}await wait(100);}assert.ok(ready,'Application did not initialize');
console.log('BROWSER CAPABILITIES',await evaluate('JSON.stringify({secureContext:isSecureContext,documentWebMCP:!!document.modelContext,navigatorWebMCP:!!navigator.modelContext,three:daollcInspection.threeStatus(),webmcp:daollcInspection.webmcpStatus(),tools:daollcInspection.toolNames()})'));
assert.match(await evaluate('daollcInspection.threeStatus()'),/WebGL/);
if(process.argv.includes('--webmcp')){
 await wait(300);
 const native=await evaluate("(async()=>{const ctx=document.modelContext;if(!ctx?.getTools)throw Error('Native WebMCP document API unavailable');const tools=await ctx.getTools();const names=tools.map(t=>t.name);const tool=tools.find(t=>t.name==='daollc_inspect_state');if(!tool)throw Error('Read-only tool not registered');const result=await ctx.executeTool(tool,JSON.stringify({}));return JSON.stringify({names,result,status:daollcInspection.webmcpStatus()});})()");
 console.log('NATIVE WEBMCP READBACK',native);const data=JSON.parse(native);assert.equal(data.names.length,4);assert.equal(JSON.parse(data.result).mode,'simulation');
}
for(const [name,width,height] of [['desktop',1440,1080],['mobile',390,1000]]){
 await rpc('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:name==='mobile'});await wait(250);
 console.log('VIEWPORT',name,await evaluate('JSON.stringify({innerWidth,scrollWidth:document.documentElement.scrollWidth})'));
 const image=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});const out=path.join(scratch,'daollc-'+name+'.png');fs.writeFileSync(out,Buffer.from(image.data,'base64'));console.log('SCREENSHOT',out);
}
await evaluate("document.getElementById('consent').checked=true;document.getElementById('consent').dispatchEvent(new Event('change'))");
if(!process.argv.includes('--webmcp')){
 assert.equal(await evaluate("document.getElementById('authorize').disabled"),true);
 assert.equal(await evaluate('daollcInspection.snapshot().status'),'IDLE');
 console.log('UI PASS: missing native WebMCP blocks operational controls');
 await rpc('Browser.close');return;
}
await click('authorize');
assert.equal(await evaluate('daollcInspection.snapshot().status'),'AUTHORIZED');await wait(700);
assert.equal(await evaluate('daollcInspection.snapshot().realized'),false);console.log('UI PASS: 650ms cannot realize authorization');
await click('execute');assert.equal(await evaluate('daollcInspection.snapshot().status'),'AWAITING_EVIDENCE');
await evaluate("document.getElementById('scenario').value='compute'");await click('witness');await click('verify');
assert.equal(await evaluate('daollcInspection.snapshot().status'),'NOT_REALIZED');console.log('UI PASS: compute receipt cannot prove legal state');
await evaluate("document.getElementById('scenario').value='valid'");await click('witness');await click('verify');assert.equal(await evaluate('daollcInspection.snapshot().status'),'VERIFIED');
assert.equal(await evaluate('daollcInspection.snapshot().realized'),false);await click('realize');
assert.equal(await evaluate('daollcInspection.snapshot().status'),'SIMULATED_REALIZED');console.log('UI PASS: realization remains explicitly simulated');
assert.equal(errors.length,0,'Browser runtime errors: '+JSON.stringify(errors));console.log('Browser runtime exceptions:',errors.length);
await rpc('Browser.close');
}catch(e){console.error(e);process.exitCode=1;if(ws&&ws.readyState===1){try{await rpc('Browser.close');}catch{}}proc.kill();}finally{if(ws)ws.close();}})();
