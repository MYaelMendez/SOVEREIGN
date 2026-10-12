// Fail-closed simulation kernel. No filing/payment/actuator adapters are connected.
(function(root){
'use strict';
const RULES=Object.freeze({
 L:{good_standing:['legal_status','good_standing'],filing_accepted:['filing_acceptance','accepted']},
 C:{runtime_execution:['runtime_result','executed'],physical_actuation:['actuator_observation','observed']},
 X:{payment_settled:['settlement_record','settled'],accounting_reconciled:['accounting_record','reconciled']},
 P:{provenance_attested:['provenance_attestation','attested']}
});
for(const domain of Object.values(RULES)){
 for(const rule of Object.values(domain))Object.freeze(rule);
 Object.freeze(domain);
}
class EnterpriseGate {
 #status='IDLE'; #request=null; #grant=null; #receipt=null;
 #tuple={L:null,C:null,X:null,P:null}; #realized=false; #verified=false;
 #revision=0; #used=new Set(); #events=[]; #mode; #now; #verifiers;
 constructor({mode='unconnected',now=()=>Date.now(),verifiers={}}={}){
  if(!['simulation','unconnected'].includes(mode))throw new Error('Unsupported mode');
  this.#mode=mode;this.#now=now;this.#verifiers={...verifiers};
 }
 get mode(){return this.#mode;} get status(){return this.#status;}
 get realized(){return this.#realized;} get tuple(){return structuredClone(this.#tuple);}
 get request(){return structuredClone(this.#request);}
 snapshot(){return {mode:this.mode,status:this.status,realized:this.realized,tuple:this.tuple,request:this.request,receipt:structuredClone(this.#receipt),events:structuredClone(this.#events)};}
 #record(type,detail){this.#events.push({type,detail,at:this.#now(),simulation:this.mode==='simulation'});}
 #checkGrant(){
  if(!this.#grant || this.#grant.expiresAt<=this.#now()){
   this.#verified=false;this.#status='EXPIRED';throw new Error('Grant absent or expired');
  }
  if(this.#status==='REVOKED')throw new Error('Grant revoked');
 }
 authorize(request,grant){
  if(this.mode!=='simulation')throw new Error('Real authorization adapter disconnected');
  if(['EXECUTING','VERIFYING'].includes(this.status))throw new Error('Operation pending');
  if(!grant?.approved || !Number.isFinite(grant.expiresAt) || grant.expiresAt<=this.#now())throw new Error('Grant absent or expired');
  if(!request?.id || !request.principal || !request.subject || !Object.hasOwn(RULES,request.domain) || !Object.hasOwn(RULES[request.domain],request.action))throw new Error('Unknown request or domain action');
  for(const key of ['principal','subject','domain','action'])if(request[key]!==grant[key])throw new Error('Grant scope mismatch');
  if(grant.requestId!==request.id)throw new Error('Grant request mismatch');
  if(this.#used.has(request.id))throw new Error('Request already realized');
  this.#request=structuredClone(request);this.#grant=structuredClone(grant);this.#receipt=null;
  this.#status='AUTHORIZED';this.#realized=false;this.#verified=false;this.#revision++;
  this.#record('AUTHORIZED','Scoped simulation grant; no enterprise truth asserted');return this.status;
 }
 async execute(){
  if(this.status!=='AUTHORIZED')throw new Error('Execution requires authorization');
  this.#checkGrant();this.#status='EXECUTING';this.#record('EXECUTE','Simulation attempt only; no external side effect');
  this.#status='AWAITING_EVIDENCE';return this.status;
 }
 witness(receipt){
  if(!['AWAITING_EVIDENCE','WITNESSED','NOT_REALIZED'].includes(this.status))throw new Error('Witness requires execution attempt');
  this.#checkGrant();this.#receipt=structuredClone(receipt);this.#verified=false;this.#revision++;
  this.#status='WITNESSED';this.#record('WITNESS','Unverified evidence received');return this.status;
 }
 async verify(){
  if(this.status!=='WITNESSED')throw new Error('Verification requires a witness');
  this.#checkGrant();const r=this.#receipt,q=this.#request,rule=RULES[q.domain][q.action];
  const rev=this.#revision;this.#status='VERIFYING';let valid=false,reason='Evidence insufficient or mismatched';
  const bound=r && r.id && r.requestId===q.id && r.subject===q.subject && r.domain===q.domain && r.action===q.action;
  const fresh=Number.isFinite(r?.observedAt) && r.observedAt<=this.#now() && this.#now()-r.observedAt<=60000;
  const predicate=r?.kind===rule[0] && r?.outcome===rule[1];
  const physical=q.action!=='physical_actuation' || (r?.actuatorAcknowledged===true && r?.outcomeObserved===true);
  if(bound && fresh && predicate && physical && r.simulation===true && !this.#used.has(r.id)){
   const verifier=this.#verifiers[q.domain];
   if(typeof verifier==='function'){
    try{valid=(await verifier(structuredClone(r),structuredClone(q)))===true;}catch(e){reason='Verifier failed: '+e.message;}
   }else reason='Domain verifier disconnected';
  }
  if(this.#revision!==rev || this.status!=='VERIFYING')return false;
  try{this.#checkGrant();}catch{this.#verified=false;return false;}
  this.#verified=valid;this.#status=valid?'VERIFIED':'NOT_REALIZED';
  this.#record('VERIFY',valid?'Simulation predicate verified by fixture verifier':reason);return valid;
 }
 realize(){
  if(this.status!=='VERIFIED' || !this.#verified)throw new Error('Realization requires verified evidence');
  this.#checkGrant();const r=this.#receipt,q=this.#request;
  this.#tuple[q.domain]={outcome:r.outcome,receiptId:r.id,requestId:q.id,observedAt:r.observedAt,simulation:true};
  this.#used.add(r.id);this.#used.add(q.id);this.#realized=true;this.#verified=false;
  this.#status='SIMULATED_REALIZED';this.#revision++;this.#record('REALIZE','Simulation tuple updated; not real enterprise status');return this.tuple;
 }
 revoke(){this.#status='REVOKED';this.#verified=false;this.#revision++;this.#record('REVOKE','Grant withdrawn');}
}
root.DAOLLC={EnterpriseGate,RULES};
if(typeof module!=='undefined')module.exports=root.DAOLLC;
})(typeof globalThis!=='undefined'?globalThis:this);
