const test=require('node:test');
const assert=require('node:assert/strict');
const {EnterpriseGate}=require('./gate.js');
const request={id:'req-1',principal:'HUMAN://ROOT',subject:'demo-enterprise',domain:'L',action:'good_standing'};
const grant={requestId:'req-1',principal:'HUMAN://ROOT',subject:'demo-enterprise',domain:'L',action:'good_standing',approved:true,expiresAt:2000};
test('authorization and elapsed time never realize enterprise state',()=>{
 let clock=1000;const g=new EnterpriseGate({mode:'simulation',now:()=>clock});
 g.authorize(request,grant);clock+=650;
 assert.equal(g.status,'AUTHORIZED');assert.equal(g.realized,false);
 assert.deepEqual(g.tuple,{L:null,C:null,X:null,P:null});
});
test('simulation realizes only after execute witness domain verification',async()=>{
 const receipt={id:'receipt-1',requestId:'req-1',subject:'demo-enterprise',domain:'L',action:'good_standing',kind:'legal_status',outcome:'good_standing',observedAt:1000,simulation:true};
 const g=new EnterpriseGate({mode:'simulation',now:()=>1000,verifiers:{L:async r=>r.id==='receipt-1'}});
 g.authorize(request,grant);await g.execute();assert.equal(g.status,'AWAITING_EVIDENCE');
 g.witness(receipt);assert.equal(g.status,'WITNESSED');assert.equal(g.realized,false);
 assert.equal(await g.verify(),true);assert.equal(g.status,'VERIFIED');assert.equal(g.realized,false);
 g.realize();assert.equal(g.status,'SIMULATED_REALIZED');assert.equal(g.tuple.L.outcome,'good_standing');
 assert.equal(g.tuple.C,null);assert.equal(g.tuple.X,null);assert.equal(g.tuple.P,null);
});
