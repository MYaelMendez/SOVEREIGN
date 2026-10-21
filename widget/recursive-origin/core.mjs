/** Local preparation model. These records never confer execution authority. */
export const ORIGIN = 'x0:y0:z0:\u00e6:\u00e6';
export const PUBLIC = 'x0:y0:z:0:\u00e6:\u00e6:\u00e6';
export const VERSION = '0.1.0';
export const BASE = '9ba31caebe5c781be03c50d069386ee4428df34d';
export function resolveEntry(raw) {
  if (typeof raw !== 'string' || raw.length > 128 || /[\u0000-\u001f\u007f\u200b-\u200f\u202a-\u202e]/u.test(raw)) return null;
  const text = raw.normalize('NFC').trim().toLowerCase().replace(/\ufe0f/gu, '');
  if (['origin', ORIGIN, '\u00e6', '$\u00e6', '$ae', '$mcp', '&mcp', '>_\u00e6\u00e6\u00e6://|||'].includes(text)) return 'origin';
  if (['public', PUBLIC].includes(text)) return 'public';
  if (['$\u2764', '@\u2764', '$@\u2764'].includes(text)) return 'intention';
  return null;
}
function checkedText(value, limit, required = false) {
  if (typeof value !== 'string' || value.length > limit || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u202a-\u202e]/u.test(value) || (required && !value.trim())) throw new Error(`Use ${required ? '1' : '0'}-${limit} characters.`);
  return value;
}
export class RecursiveOrigin {
  #nodes = new Map(); #serial = 0; #revision = 0; #reviewed = null;
  constructor() {
    this.#nodes.set('origin', {id:'origin', parent:null, depth:0, name:'Open Sovereign / ^\u00e6', intent:'', executor:'ae'});
  }
  get revision() { return this.#revision; }
  get nodes() { return [...this.#nodes.values()].map(node => ({...node})); }
  node(id) {
    const node = this.#nodes.get(id);
    if (!node) throw new Error('Unknown environment.');
    return {...node};
  }
  #changed() { this.#revision++; this.#reviewed = null; }
  update(id, changes) {
    if (!changes || typeof changes !== 'object' || Array.isArray(changes) || Object.keys(changes).some(key => !['name','intent','executor'].includes(key))) throw new Error('Only name, intention and executor preference may be edited.');
    const next = this.node(id);
    if ('name' in changes) next.name = checkedText(changes.name, 80, true);
    if ('intent' in changes) next.intent = checkedText(changes.intent, 600);
    if ('executor' in changes) {
      if (!['ae','codex'].includes(changes.executor)) throw new Error('Unsupported executor preference.');
      next.executor = changes.executor;
    }
    this.#nodes.set(id,next); this.#changed();
  }
  addChild(parentId, copyContext = false) {
    if (typeof copyContext !== 'boolean') throw new Error('Context copying needs an explicit boolean.');
    const parent = this.node(parentId);
    if (parent.depth >= 4 || this.#nodes.size >= 24) throw new Error('This local prototype is bounded to depth 4 and 24 environments.');
    const id = `child-${++this.#serial}`;
    this.#nodes.set(id,{id,parent:parent.id,depth:parent.depth+1,name:`Environment ${this.#serial}`,intent:copyContext ? parent.intent : '',executor:parent.executor});
    this.#changed(); return id;
  }
  clearPrivateContext() {
    for (const node of this.#nodes.values()) node.intent = '';
    this.#changed();
  }
  projection() {
    return {
      schema:'ae.recursive-public-draft.v1', version:VERSION,
      coordinates:{origin:ORIGIN, public:PUBLIC},
      source:{repository:'MYaelMendez/SOVEREIGN',inspected_base_revision:BASE},
      environments:this.nodes.map(n => ({id:n.id,parent:n.parent,depth:n.depth,display_name:n.name,executor_preference:n.executor,connection:'not_verified',authorization:null})),
      authority:{principal:'human',inherit:false,grant:null},
      publication:{state:'draft',deployment_authorized:false},
      witness:{kind:'local_preparation',external_success:false,attestation:false},
      purpose:'Return value to the human.'
    };
  }
  prepare() { return JSON.stringify(this.projection(),null,2) + '\n'; }
  review(exactText) {
    if (exactText !== this.prepare()) throw new Error('The preview changed. Prepare and review it again.');
    this.#reviewed = {revision:this.#revision,text:exactText};
  }
  revokeReview() { this.#reviewed = null; }
  exportReviewed() {
    if (!this.#reviewed || this.#reviewed.revision !== this.#revision || this.#reviewed.text !== this.prepare()) throw new Error('Review this exact public draft before downloading.');
    return this.#reviewed.text;
  }
}
