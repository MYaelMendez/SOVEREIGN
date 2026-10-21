import {RecursiveOrigin, resolveEntry, ORIGIN, PUBLIC} from './core.mjs';
const mounted = new WeakMap();
/** Insert a sibling above an existing element; never replace or reparent it. */
export function mountBefore(origin) {
  if (!(origin instanceof Element) || !origin.isConnected || !origin.parentElement) throw new Error('An existing connected origin element is required.');
  if (mounted.has(origin)) return mounted.get(origin);
  const previousFocus = document.activeElement;
  const host = document.createElement('ae-recursive-origin');
  const root = host.attachShadow({mode:'open'});
  const model = new RecursiveOrigin();
  let selected = 'origin', prepared = null, destroyed = false;
  const byId = id => root.getElementById(id);
  // Static owned template. User strings only enter value/textContent below.
  root.innerHTML = `<style>
:host{display:block;width:min(100%,520px);margin:20px auto;color:#f2eee3;font:15px/1.5 system-ui,sans-serif;--gold:#d4af37;--line:#665729}
*{box-sizing:border-box}[hidden]{display:none!important}
.frame{aspect-ratio:9/16;display:grid;grid-template-rows:auto minmax(0,1fr) auto;border:1px solid var(--gold);background:#080907;box-shadow:0 20px 50px #0006;overflow:hidden}
header,footer{padding:16px;border-bottom:1px solid var(--line)}footer{border-top:1px solid var(--line);border-bottom:0;font-size:12px;color:#ded3b8}.scroll{overflow:auto;min-height:0;padding:16px;overscroll-behavior:contain}
h2{font-size:25px;line-height:1.12;margin:7px 0 10px;letter-spacing:-.03em}p{margin:8px 0}.kicker{font:11px/1.5 ui-monospace,monospace;color:#ead68a;letter-spacing:.06em}.muted{font-size:12px;color:#d2cbb9}code{font-size:12px;overflow-wrap:anywhere;white-space:normal}
label{display:block;margin:10px 0 4px;font-weight:650;font-size:13px}input,select,textarea,button{font:inherit}input:not([type=checkbox]),select,textarea{width:100%;min-width:0;border:1px solid var(--line);background:#15170f;color:inherit;padding:10px;accent-color:var(--gold)}textarea{min-height:105px;resize:vertical}input[type=checkbox]{min-width:20px;min-height:20px;accent-color:var(--gold)}
button{min-height:44px;cursor:pointer;background:#1c2113;color:#f2eee3;border:1px solid var(--line);padding:9px 12px}button:disabled{opacity:.5;cursor:not-allowed}button.primary{background:var(--gold);color:#101108;font-weight:750}button[aria-pressed=true]{border-color:var(--gold);background:#373018}:focus-visible{outline:3px solid #9ee1ff;outline-offset:3px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.row>*{flex:1;min-width:0}.check{display:flex;align-items:flex-start;gap:8px;font-size:12px;font-weight:400}.children{display:flex;overflow-x:auto;gap:10px;scroll-snap-type:x mandatory;padding:6px 0 12px}.child{flex:0 0 100px;aspect-ratio:9/16;scroll-snap-align:start;text-align:left;display:flex;flex-direction:column;justify-content:space-between;overflow-wrap:anywhere}.child strong{font-size:13px}.child small{font-size:11px;color:#e5d59d}
pre{max-height:310px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace;border:1px solid var(--line);padding:10px;background:#14160f}.status{font-size:12px;color:#b9eccd}.command{display:flex;gap:6px}.command input{flex:1;width:0}.command button{flex:none}.crumb{font-size:12px;color:#e5d59d}
</style>
<section class="frame" aria-label="Recursive origin widget">
<header><div class="kicker">OPEN SOVEREIGN / ^\u00e6 / &gt;_\u00e6\u00e6\u00e6://|||</div><h2>Build forward.<br>Preserve backward.</h2><div class="row"><button id="origin-view" aria-pressed="true">Origin</button><button id="public-view" aria-pressed="false">Public review</button></div><code id="coordinate"></code></header>
<div class="scroll"><div id="trail" class="crumb"></div><form id="command"><label for="entry">Symbolic entry</label><div class="command"><input id="entry" value="$mcp" maxlength="128" autocomplete="off" spellcheck="false"><button>Go</button></div></form>
<div id="local-pane"><label for="name">Public environment name</label><input id="name" maxlength="80" autocomplete="off"><label for="intent">$\u2764\ufe0f / What should this return to the human?</label><textarea id="intent" maxlength="600" autocomplete="off" placeholder="Your intention stays in this tab."></textarea><label for="executor">Preferred executor after setup</label><select id="executor"><option value="ae">\u00e6 / default</option><option value="codex">Codex / preference only</option></select><p class="muted">No runtime is connected. Names appear in public drafts; private intentions do not.</p>
<label class="check"><input id="copy-context" type="checkbox"><span>Copy this intention into the child, in this tab only. No authority travels.</span></label><div class="row"><button id="child" class="primary">Add child environment</button><button id="parent">Back to parent</button></div><nav id="children" class="children" aria-label="Child environments"></nav><button id="clear">Clear all private intentions</button></div>
<div id="public-pane" hidden><p class="muted">Preview the public structure, not your private conversation. Review allows a local download only.</p><button id="prepare" class="primary">Prepare public draft</button><pre id="preview" tabindex="0">No public draft prepared.</pre><label class="check"><input id="approve" type="checkbox" disabled><span>I approve downloading this exact draft. Publishing requires separate approval.</span></label><button id="download" disabled>Download reviewed draft</button></div>
<p id="status" class="status" role="status" aria-live="polite">Local preparation. Nothing published.</p></div>
<footer><strong>Return value to the human. \u2764\ufe0f</strong><br>Many agents. One principal.<div class="row"><button id="remove">Remove this layer</button></div></footer></section>`;
  function status(message) { byId('status').textContent = message; }
  function invalidate() {
    prepared = null; model.revokeReview(); byId('approve').checked = false;
    byId('approve').disabled = true; byId('download').disabled = true;
    byId('preview').textContent = 'No public draft prepared.';
  }
  function mode(view) {
    const pub = view === 'public';
    byId('local-pane').hidden = pub; byId('public-pane').hidden = !pub;
    byId('origin-view').setAttribute('aria-pressed',String(!pub));
    byId('public-view').setAttribute('aria-pressed',String(pub));
    byId('coordinate').textContent = pub ? PUBLIC : ORIGIN;
  }
  function refresh() {
    const node = model.node(selected);
    byId('name').value = node.name; byId('intent').value = node.intent;
    byId('executor').value = node.executor; byId('parent').disabled = !node.parent;
    byId('child').disabled = node.depth >= 4 || model.nodes.length >= 24;
    byId('trail').textContent = `${node.id} / depth ${node.depth} / ${model.nodes.length} environments`;
    byId('children').replaceChildren();
    for (const child of model.nodes.filter(n => n.parent === selected)) {
      const button = document.createElement('button'); button.className = 'child';
      const name = document.createElement('strong'); name.textContent = child.name;
      const detail = document.createElement('small'); detail.textContent = `Depth ${child.depth}\n${child.id}\nNo grant`;
      button.append(name, detail); button.addEventListener('click',() => {selected = child.id; refresh();});
      byId('children').append(button);
    }
  }
  function edit(key, value) {
    invalidate();
    try {model.update(selected,{[key]:value}); status('Updated in this tab. Public review reset.');}
    catch(error) {status(error.message);}
  }
  byId('name').addEventListener('input',e => edit('name',e.target.value));
  byId('intent').addEventListener('input',e => edit('intent',e.target.value));
  byId('executor').addEventListener('change',e => edit('executor',e.target.value));
  byId('child').addEventListener('click',() => {
    try {const id = model.addChild(selected,byId('copy-context').checked); invalidate(); byId('copy-context').checked = false; refresh(); status(`${id} added. Select its portrait card to enter it.`);}
    catch(error) {status(error.message);}
  });
  byId('parent').addEventListener('click',() => {selected = model.node(selected).parent || 'origin'; refresh();});
  byId('clear').addEventListener('click',() => {model.clearPrivateContext(); invalidate(); refresh(); status('Private intentions cleared. Previously downloaded files are unchanged.');});
  byId('origin-view').addEventListener('click',() => mode('origin'));
  byId('public-view').addEventListener('click',() => mode('public'));
  byId('command').addEventListener('submit',event => {
    event.preventDefault(); const route = resolveEntry(byId('entry').value);
    if (!route) return status('Unknown entry. Use $mcp, &mcp, $ae, $\u00e6, $\u2764\ufe0f, origin or public.');
    mode(route); status('View selected. No navigation, permission change or external action.');
    if (route === 'intention') byId('intent').focus();
  });
  byId('prepare').addEventListener('click',() => {invalidate(); prepared = model.prepare(); byId('preview').textContent = prepared; byId('approve').disabled = false; status('Public draft prepared locally.');});
  byId('approve').addEventListener('change',event => {
    try {if(event.target.checked) model.review(prepared); else model.revokeReview(); byId('download').disabled = !event.target.checked;}
    catch(error) {invalidate(); status(error.message);}
  });
  byId('download').addEventListener('click',() => {
    try {
      const text = model.exportReviewed(), url = URL.createObjectURL(new Blob([text],{type:'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = 'ae-recursive-public-draft.json';
      root.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
      status('Local download requested. No publication, filing, payment or signed attestation.');
    } catch(error) {status(error.message);}
  });
  const handle = Object.freeze({element:host,destroy() {
    if(destroyed) return; destroyed = true; model.clearPrivateContext(); root.replaceChildren(); host.remove(); mounted.delete(origin);
    if(previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({preventScroll:true});
  }});
  byId('remove').addEventListener('click',handle.destroy);
  origin.before(host); mounted.set(origin,handle); mode('origin'); refresh(); return handle;
}
