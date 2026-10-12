const test=require('node:test');const assert=require('node:assert/strict');
const {EnterpriseGate,RULES}=require('./gate.js');
function fixture(domain='L',action='good_standing',verifier=async()=>true){
 let time=1000;const g=new EnterpriseGate({mode:'simulation',now:()=>time,verifiers:{[domain]:verifier}});
 const q={id:'r',principal:'HUMAN://ROOT',subject:'demo',domain,action};
 const a={...q,requestId:q.id,approved:true,expiresAt:2000};
 const r={id:'w',requestId:q.id,subject:q.subject,domain,action,kind:RULES[domain][action][0],outcome:RULES[domain][action][1],observedAt:1000,simulation:true};
 return {g,q,a,r,setTime:v=>time=v};
}
async function witness(f,changes={}){f.g.authorize(f.q,f.a);await f.g.execute();f.g.witness({...f.r,...changes});return f.g.verify();}
test('real mode is disconnected and cannot accept a UI grant',()=>{const f=fixture();assert.throws(()=>new EnterpriseGate().authorize(f.q,f.a),/disconnected/);});
test('grant cannot authorize a different subject',()=>{const f=fixture();assert.throws(()=>f.g.authorize(f.q,{...f.a,subject:'other'}),/scope/);});
test('missing expiry is denied',()=>{const f=fixture();assert.throws(()=>f.g.authorize(f.q,{...f.a,expiresAt:undefined}),/expired/);});
test('execute without authorization is denied',async()=>{await assert.rejects(new EnterpriseGate({mode:'simulation'}).execute(),/authorization/);});
test('witness cannot bypass execution',()=>{const f=fixture();f.g.authorize(f.q,f.a);assert.throws(()=>f.g.witness(f.r),/execution/);});
test('realize cannot bypass verification',async()=>{const f=fixture();f.g.authorize(f.q,f.a);await f.g.execute();f.g.witness(f.r);assert.throws(()=>f.g.realize(),/verified/);});
test('compute receipt cannot establish legal good standing',async()=>{const f=fixture();assert.equal(await witness(f,{domain:'C',kind:'runtime_result',outcome:'executed'}),false);assert.equal(f.g.tuple.L,null);});
test('filing submission is not state acceptance',async()=>{const f=fixture('L','filing_accepted');assert.equal(await witness(f,{kind:'filing_submission',outcome:'submitted'}),false);});
test('payment initiation is not settlement',async()=>{const f=fixture('X','payment_settled');assert.equal(await witness(f,{kind:'payment_intent',outcome:'initiated'}),false);});
test('actuator command acknowledgment alone is not physical outcome',async()=>{const f=fixture('C','physical_actuation');assert.equal(await witness(f,{actuatorAcknowledged:true,outcomeObserved:false}),false);});
test('witness with wrong request binding is rejected',async()=>{assert.equal(await witness(fixture(),{requestId:'other'}),false);});
test('old witness is rejected',async()=>{assert.equal(await witness(fixture(),{observedAt:-60000}),false);});
test('future-dated witness is rejected',async()=>{assert.equal(await witness(fixture(),{observedAt:1001}),false);});
test('receipt without simulation label cannot enter demo tuple',async()=>{assert.equal(await witness(fixture(),{simulation:false}),false);});
test('untrusted verifier failure cannot be promoted',async()=>{assert.equal(await witness(fixture('L','good_standing',async()=>false)),false);});
test('disconnected verifier fails closed',async()=>{const f=fixture();f.g=new EnterpriseGate({mode:'simulation',now:()=>1000});assert.equal(await witness(f),false);});
test('grant expiry between verify and realize blocks commit',async()=>{const f=fixture();assert.equal(await witness(f),true);f.setTime(2001);assert.throws(()=>f.g.realize(),/expired/);assert.equal(f.g.tuple.L,null);});
test('revocation between verify and realize blocks commit',async()=>{const f=fixture();await witness(f);f.g.revoke();assert.throws(()=>f.g.realize(),/verified/);});
test('revocation during asynchronous verification is preserved',async()=>{let release;const f=fixture('L','good_standing',()=>new Promise(r=>release=r));f.g.authorize(f.q,f.a);await f.g.execute();f.g.witness(f.r);const pending=f.g.verify();f.g.revoke();release(true);assert.equal(await pending,false);assert.equal(f.g.status,'REVOKED');});
test('realized request cannot be replayed',async()=>{const f=fixture();await witness(f);f.g.realize();assert.throws(()=>f.g.authorize(f.q,f.a),/already/);});
test('snapshot mutation cannot alter enterprise tuple',async()=>{const f=fixture();await witness(f);f.g.realize();const t=f.g.tuple;t.L.outcome='forged';assert.equal(f.g.tuple.L.outcome,'good_standing');});
for(const [domain,action] of [['C','runtime_execution'],['X','payment_settled'],['P','provenance_attested']])test(domain+' valid demo receipt changes only its domain',async()=>{const f=fixture(domain,action);assert.equal(await witness(f),true);f.g.realize();for(const key of ['L','C','X','P'])assert.equal(f.g.tuple[key]!==null,key===domain);});
