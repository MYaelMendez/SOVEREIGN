// >_æ| command registry
// the URL is the command. the namespace is the runtime.

const COMMANDS = [
  // ── blueprints ──
  {
    id: 'startabusiness',
    pattern: /^#startabusiness$/,
    icon: 'æ',
    title: '#startabusiness',
    desc: 'generate agentic.html sovereign business page',
    url: 'https://myaelmendez.github.io/ae/',
    keywords: ['business', 'llc', 'dao', 'form', 'start']
  },
  {
    id: 'sovaereign',
    pattern: /^#sovaereign$/,
    icon: 'sv',
    title: '#sovaereign',
    desc: "the entrepreneur's first repo — GitHub App",
    url: 'https://github.com/apps/sovaereign',
    keywords: ['repo', 'github', 'scaffold', 'git']
  },

  // ── stack ──
  {
    id: 'hermes',
    pattern: /^(>_h|hermes)$/,
    icon: 'h',
    title: '>_h · Hermes',
    desc: 'intent routing — Nous Research',
    url: 'https://hermes-agent.nousresearch.com',
    keywords: ['agent', 'nous', 'chat', 'ai']
  },
  {
    id: 'nvidia',
    pattern: /^(>_n|nvidia|nim)$/,
    icon: 'n',
    title: '>_n · NVIDIA',
    desc: 'compute — NIM API / build.nvidia.com',
    url: 'https://build.nvidia.com',
    keywords: ['gpu', 'nim', 'llm', 'inference']
  },
  {
    id: 'stripe',
    pattern: /^(>_\$|rails|affiliate|\$^æ)$/,
    icon: '$',
    title: '>_$ · Doola affiliate',
    desc: 'financial rail — Doola affiliate (paid, zero custody). Stripe = future plugin.',
    url: 'https://partnersps.doola.com/hhsoqhb23250',
    keywords: ['pay', 'money', 'affiliate', 'doola', 'formation', 'rail']
  },

  // ── namespace ──
  {
    id: 'aestore',
    pattern: /^(æ\.store|aestore|æ)$/,
    icon: 'æ',
    title: 'æ.store',
    desc: 'the namespace — run, url source',
    url: 'https://myaelmendez.github.io/ae/',
    keywords: ['store', 'app', 'viewport', 'boot']
  },
  {
    id: 'llmstore',
    pattern: /^(llm\.store|llmstore)$/,
    icon: 'll',
    title: 'llm.store',
    desc: 'the namespace — find, well-known endpoint',
    url: 'https://myaelmendez.github.io/domain-stack.json',
    keywords: ['find', 'endpoint', 'well-known', 'api']
  },
  {
    id: 'clillc',
    pattern: /^cli\.llc$/,
    icon: 'cl',
    title: 'cli.llc',
    desc: 'command line infrastructure',
    url: 'https://myaelmendez.github.io/ae/',
    keywords: ['cli', 'command', 'infrastructure']
  },
  {
    id: 'aeaeae',
    pattern: /^(æææ|æææ\.com)$/,
    icon: 'ææ',
    title: 'æææ.com',
    desc: 'the triple glyph',
    url: 'https://myaelmendez.github.io/ae/',
    keywords: ['triple', 'glyph', 'brand']
  },

  // ── blueprints live ──
  {
    id: 'primitive',
    pattern: /^primitive$/,
    icon: '+æ',
    title: 'PRIMITIVE.md',
    desc: 'AEL primitives: +æ ^æ $^æ # $',
    url: 'https://myaelmendez.github.io/PRIMITIVE.md',
    keywords: ['primitive', 'syntax', 'notation', 'ael']
  },
  {
    id: 'skill',
    pattern: /^(skill|SKILL\.md)$/,
    icon: 'sk',
    title: 'SKILL.md',
    desc: 'the self-contained Hermes skill',
    url: 'https://myaelmendez.github.io/SKILL.md',
    keywords: ['skill', 'hermes', 'install', 'self']
  },
  {
    id: 'domainstack',
    pattern: /^(domains?|stack)$/,
    icon: 'dsn',
    title: 'domain-stack.json',
    desc: '13 domains — the syntax stack',
    url: 'https://myaelmendez.github.io/domain-stack.json',
    keywords: ['domain', 'dns', 'hostinger', 'stack']
  },

  // ── social ──
  {
    id: 'x',
    pattern: /^(x|twitter|@l_net801)$/,
    icon: '𝕏',
    title: '@l_net801',
    desc: 'æ.store on X',
    url: 'https://x.com/l_net801',
    keywords: ['twitter', 'social', 'post']
  },
  {
    id: 'github',
    pattern: /^(gh|github)$/,
    icon: 'gh',
    title: 'MYaelMendez',
    desc: 'GitHub — the repo is the business',
    url: 'https://github.com/MYaelMendez',
    keywords: ['code', 'repo', 'pr', 'commit']
  },

  // ── NAICS ──
  {
    id: 'naics',
    pattern: /^#naics$/,
    icon: 'ná',
    title: '#naics',
    desc: 'business classification lookup',
    url: 'https://www.census.gov/naics/',
    keywords: ['naics', 'classify', 'code', 'industry']
  },

  // ── cmd+k search ──
  {
    id: 'cmdk',
    pattern: /^(cmd\+k|search|find)$/,
    icon: '⌘',
    title: 'Cmd+K · search()',
    desc: 'search the domain stack — Code Mode',
    url: 'https://myaelmendez.github.io/domain-stack.json',
    keywords: ['search', 'find', 'code mode', 'cmd']
  }
];

// Fuzzy search: match against id, title, desc, keywords
function searchCommands(query) {
  if (!query) return COMMANDS.slice(0, 8);

  const q = query.toLowerCase().replace(/^>\s*/, '');

  // Exact pattern match first
  for (const cmd of COMMANDS) {
    if (cmd.pattern.test(q)) return [cmd, ...COMMANDS.filter(c => c.id !== cmd.id).slice(0, 4)];
  }

  // Fuzzy: score by how many terms match
  const terms = q.split(/\s+/);
  const scored = COMMANDS.map(cmd => {
    const haystack = [cmd.id, cmd.title, cmd.desc, ...cmd.keywords].join(' ').toLowerCase();
    const score = terms.reduce((acc, t) => acc + (haystack.includes(t) ? 1 : 0), 0);
    return { cmd, score };
  })
  .filter(s => s.score > 0)
  .sort((a, b) => b.score - a.score)
  .map(s => s.cmd);

  return scored.slice(0, 8);
}
