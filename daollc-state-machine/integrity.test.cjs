'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {EnterpriseGate,RULES}=require('./gate.js');
test('inherited object methods cannot become enterprise predicates',()=>{
 const g=new EnterpriseGate({mode:'simulation',now:()=>1000});
 const q={id:'r',principal:'HUMAN://ROOT',subject:'demo',domain:'L',action:'toString'};
 const a={...q,requestId:'r',approved:true,expiresAt:2000};
 assert.throws(()=>g.authorize(q,a),/Unknown/);
});
test('exported evidence requirements cannot be mutated',()=>{
 assert.throws(()=>{RULES.L.good_standing[1]='settled';},TypeError);
 assert.throws(()=>{RULES.L.filing_accepted=['filing_submission','submitted'];},TypeError);
});
