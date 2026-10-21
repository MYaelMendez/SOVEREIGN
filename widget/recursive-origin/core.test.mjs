import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {RecursiveOrigin, resolveEntry, ORIGIN, PUBLIC, VERSION} from './core.mjs';
test('exact origin and public notation remain distinct',()=>{
 assert.equal(ORIGIN,'x0:y0:z0:\u00e6:\u00e6'); assert.equal(PUBLIC,'x0:y0:z:0:\u00e6:\u00e6:\u00e6');
 assert.equal(resolveEntry(ORIGIN),'origin'); assert.equal(resolveEntry(PUBLIC),'public');
});
test('entry aliases share local origin; heart routes to intention',()=>{
 for(const alias of ['\u00e6','$\u00e6','$ae','$mcp','&mcp','$MCP']) assert.equal(resolveEntry(alias),'origin');
 for(const alias of ['$\u2764\ufe0f','@\u2764\ufe0f','$@\u2764\ufe0f']) assert.equal(resolveEntry(alias),'intention');
});
test('unknown and malformed commands do not dispatch',()=>{
 for(const entry of ['',null,{},'delete all','x'.repeat(129),'$mcp\n','\u202e$mcp']) assert.equal(resolveEntry(entry),null);
});
test('children preserve lineage; context copy is opt-in',()=>{
 const m=new RecursiveOrigin();m.update('origin',{intent:'PRIVATE_PARENT',executor:'codex'});
 const a=m.addChild('origin'),b=m.addChild('origin',true);
 assert.equal(m.node(a).intent,'');assert.equal(m.node(b).intent,'PRIVATE_PARENT');
 assert.equal(m.node(a).parent,'origin');assert.equal(m.node(a).executor,'codex');
 assert.equal(m.projection().environments[1].authorization,null);
});
test('recursion is bounded',()=>{
 const m=new RecursiveOrigin();let id='origin';for(let i=0;i<4;i++)id=m.addChild(id);
 assert.throws(()=>m.addChild(id),/bounded/);
 const n=new RecursiveOrigin();for(let i=0;i<23;i++)n.addChild('origin');assert.throws(()=>n.addChild('origin'),/bounded/);
});
test('snapshot cannot mutate internal state',()=>{
 const m=new RecursiveOrigin(),n=m.nodes;n[0].name='MUTATED';assert.notEqual(m.node('origin').name,'MUTATED');
});
test('grant or unknown field imports are rejected',()=>{
 const m=new RecursiveOrigin();assert.throws(()=>m.update('origin',{grant:'ALL'}));assert.throws(()=>m.update('origin',{executor:'shell'}));
 assert.throws(()=>m.update('origin',{name:''}));assert.throws(()=>m.addChild('origin','true'));
});
test('public projection contains no private intention or inferred success',()=>{
 const m=new RecursiveOrigin();m.update('origin',{intent:'DO_NOT_EXPORT'});m.addChild('origin',true);const p=m.prepare();
 assert.ok(!p.includes('DO_NOT_EXPORT'));assert.ok(!p.includes('"intent"'));assert.equal(m.projection().publication.deployment_authorized,false);
 assert.equal(m.projection().authority.inherit,false);assert.equal(m.projection().witness.external_success,false);
});
test('exact preview approval is required for export',()=>{
 const m=new RecursiveOrigin();assert.throws(()=>m.exportReviewed(),/Review/);assert.throws(()=>m.review('{}'),/changed/);
 const text=m.prepare();m.review(text);assert.equal(m.exportReviewed(),text);m.revokeReview();assert.throws(()=>m.exportReviewed());
});
test('every edit invalidates prior public review',()=>{
 const m=new RecursiveOrigin();m.review(m.prepare());m.update('origin',{intent:'even a private edit'});assert.throws(()=>m.exportReviewed());
 m.review(m.prepare());m.addChild('origin');assert.throws(()=>m.exportReviewed());
});
test('clear private context preserves structure',()=>{
 const m=new RecursiveOrigin();m.update('origin',{intent:'secret'});m.addChild('origin',true);m.clearPrivateContext();
 assert.equal(m.nodes.length,2);assert.ok(m.nodes.every(n=>n.intent===''));
});
test('manifest matches implemented module and coordinates',()=>{
 const data=JSON.parse(readFileSync(new URL('./manifest.json',import.meta.url),'utf8'));
 assert.equal(data.identity.version,VERSION);assert.equal(data.interface.origin,ORIGIN);assert.equal(data.interface.public,PUBLIC);
 assert.equal(data.trust.authority,'human');assert.equal(data.trust.inherit_authority,false);
});
