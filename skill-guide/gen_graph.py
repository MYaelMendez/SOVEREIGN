#!/usr/bin/env python3
"""Generate skill-graph.html with navigation + convert-to-skill."""
import json

path = "C:/æ/skill-guide/skill-graph.html"

nodes = [
    {"id":"ae-as-skill","g":"sovereign","col":"#D4AF37","deg":12,"sz":11,"sov":True,"fleet":False,"ln":211,"tags":["ae","sovereign","stack"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/sovereign/ae-as-skill/SKILL.md","url":None},
    {"id":"cri-index","g":"sovereign","col":"#D4AF37","deg":5,"sz":8,"sov":True,"fleet":False,"ln":62,"tags":["cri","consumer","redline","index","economic"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/sovereign/cri-index/SKILL.md","url":None},
    {"id":"mail-agent","g":"sovereign","col":"#D4AF37","deg":4,"sz":8,"sov":True,"fleet":False,"ln":45,"tags":["mail","email","imap","smtp","triage"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/email/mail-agent/SKILL.md","url":None},
    {"id":"deploy-surfaces","g":"sovereign","col":"#D4AF37","deg":8,"sz":9,"sov":True,"fleet":False,"ln":180,"tags":["deploy","github-pages","surface"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/deploy-surfaces/SKILL.md","url":None},
    {"id":"glocal-mesh","g":"sovereign","col":"#D4AF37","deg":7,"sz":9,"sov":True,"fleet":False,"ln":150,"tags":["mesh","glocal","topology","tier"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/glocal-mesh/SKILL.md","url":None},
    {"id":"rtx-telemetry","g":"sovereign","col":"#D4AF37","deg":4,"sz":7,"sov":True,"fleet":False,"ln":80,"tags":["rtx","telemetry","nvidia","gpu"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/rtx-telemetry/SKILL.md","url":None},
    {"id":"sovereign-cuda-bridge","g":"sovereign","col":"#D4AF37","deg":3,"sz":6,"sov":True,"fleet":False,"ln":60,"tags":["cuda","bridge","sovereign"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/sovereign-cuda-bridge/SKILL.md","url":None},
    {"id":"html-as-skill","g":"sovereign","col":"#D4AF37","deg":6,"sz":8,"sov":True,"fleet":False,"ln":95,"tags":["html","viewport","surface"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/html-as-skill/SKILL.md","url":None},
    {"id":"qr-as-skill","g":"sovereign","col":"#D4AF37","deg":5,"sz":7,"sov":True,"fleet":False,"ln":70,"tags":["qr","key","contract","infrastructure"],"type":"skill","path":"C:/Users/yaelm/AppData/Local/hermes/skills/qr-as-skill/SKILL.md","url":None},
    {"id":"hermes-agent","g":"fleet","col":"#00ff9d","deg":10,"sz":10,"sov":False,"fleet":True,"ln":214,"tags":["hermes","agent","intent"],"type":"skill","path":None,"url":None},
    {"id":"claude-code","g":"fleet","col":"#00ff9d","deg":6,"sz":8,"sov":False,"fleet":True,"ln":755,"tags":["claude","code","delegate"],"type":"skill","path":None,"url":None},
    {"id":"opencode","g":"fleet","col":"#00ff9d","deg":5,"sz":7,"sov":False,"fleet":True,"ln":220,"tags":["opencode","delegate"],"type":"skill","path":None,"url":None},
    {"id":"agentic-interpreter","g":"fleet","col":"#00ff9d","deg":4,"sz":7,"sov":False,"fleet":True,"ln":219,"tags":["interpreter","delegate"],"type":"skill","path":None,"url":None},
    {"id":"agentic-entrepreneurship","g":"business","col":"#de7a48","deg":8,"sz":10,"sov":False,"fleet":False,"ln":1367,"tags":["agentic","business","entrepreneurship"],"type":"skill","path":None,"url":None},
    {"id":"domain-codemode","g":"business","col":"#de7a48","deg":5,"sz":7,"sov":False,"fleet":False,"ln":126,"tags":["domain","codemode"],"type":"skill","path":None,"url":None},
    {"id":"aipodcast_me/index.html","g":"pages","col":"#48deac","deg":3,"sz":6,"sov":False,"fleet":False,"ln":580,"tags":["surface","hq","gold-on-void"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/index.html"},
    {"id":"aipodcast_me/discover.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":400,"tags":["surface","webgpu","torus"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/discover.html"},
    {"id":"aipodcast_me/loop.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":350,"tags":["surface","webgpu","webllm"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/loop.html"},
    {"id":"aipodcast_me/cri_surface.html","g":"pages","col":"#48deac","deg":3,"sz":6,"sov":False,"fleet":False,"ln":302,"tags":["surface","cri","economic"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/cri_surface.html"},
    {"id":"aipodcast_me/vscoder.html","g":"pages","col":"#48deac","deg":4,"sz":7,"sov":False,"fleet":False,"ln":613,"tags":["surface","vscoder","engineering"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/vscoder.html"},
    {"id":"aipodcast_me/skill-graph.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":195,"tags":["surface","graph","topology"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/skill-graph.html"},
    {"id":"aipodcast_me/qr_keys.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":580,"tags":["surface","qr","keys"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/qr_keys.html"},
    {"id":"keeper.html","g":"pages","col":"#48deac","deg":3,"sz":6,"sov":False,"fleet":False,"ln":200,"tags":["surface","keeper","custodian"],"type":"page","path":None,"url":"https://myaelmendez.github.io/keeper.html"},
    {"id":"constellation.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":180,"tags":["surface","webgpu","mesh"],"type":"page","path":None,"url":"https://myaelmendez.github.io/constellation.html"},
    {"id":"markets.html","g":"pages","col":"#48deac","deg":2,"sz":5,"sov":False,"fleet":False,"ln":250,"tags":["surface","markets","data"],"type":"page","path":None,"url":"https://myaelmendez.github.io/aipodcast_me/markets.html"},
    {"id":"ae_code_mode.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":463,"tags":["code-mode","sandbox"],"type":"page","path":"C:/æ/agents/æ_code_mode.py","url":None},
    {"id":"cri_engine.py","g":"standalone","col":"#debe48","deg":3,"sz":6,"sov":False,"fleet":False,"ln":644,"tags":["cri","engine","calculate"],"type":"page","path":"C:/æ/agents/cri_engine.py","url":None},
    {"id":"cri_server.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":352,"tags":["cri","api","server"],"type":"page","path":"C:/æ/agents/cri_server.py","url":None},
    {"id":"qr_key_manager.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":457,"tags":["qr","keys","ed25519"],"type":"page","path":"C:/æ/agents/qr_key_manager.py","url":None},
    {"id":"contract_qr.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":480,"tags":["qr","contracts","multisig"],"type":"page","path":"C:/æ/agents/contract_qr.py","url":None},
    {"id":"qr_server.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":379,"tags":["qr","api","server"],"type":"page","path":"C:/æ/agents/qr_server.py","url":None},
    {"id":"mail_agent.py","g":"standalone","col":"#debe48","deg":3,"sz":6,"sov":False,"fleet":False,"ln":501,"tags":["mail","agent","smtp"],"type":"page","path":"C:/æ/agents/mail_agent.py","url":None},
    {"id":"keeper_email.py","g":"standalone","col":"#debe48","deg":2,"sz":5,"sov":False,"fleet":False,"ln":280,"tags":["keeper","email","delivery"],"type":"page","path":"C:/æ/agents/keeper_email.py","url":None},
]

edges = [
    {"s":"ae-as-skill","t":"cri-index","w":3},{"s":"ae-as-skill","t":"mail-agent","w":2},{"s":"ae-as-skill","t":"deploy-surfaces","w":3},{"s":"ae-as-skill","t":"glocal-mesh","w":3},{"s":"ae-as-skill","t":"html-as-skill","w":2},{"s":"ae-as-skill","t":"qr-as-skill","w":2},{"s":"ae-as-skill","t":"rtx-telemetry","w":2},{"s":"ae-as-skill","t":"sovereign-cuda-bridge","w":2},
    {"s":"cri-index","t":"mail-agent","w":2},{"s":"deploy-surfaces","t":"glocal-mesh","w":2},{"s":"html-as-skill","t":"qr-as-skill","w":2},
    {"s":"aipodcast_me/cri_surface.html","t":"cri-index","w":3},{"s":"aipodcast_me/vscoder.html","t":"ae-as-skill","w":3},{"s":"aipodcast_me/qr_keys.html","t":"qr-as-skill","w":3},{"s":"keeper.html","t":"mail-agent","w":2},{"s":"aipodcast_me/skill-graph.html","t":"ae-as-skill","w":2},
    {"s":"aipodcast_me/index.html","t":"aipodcast_me/discover.html","w":1},{"s":"aipodcast_me/index.html","t":"aipodcast_me/loop.html","w":1},{"s":"aipodcast_me/index.html","t":"aipodcast_me/cri_surface.html","w":1},{"s":"aipodcast_me/index.html","t":"aipodcast_me/vscoder.html","w":1},{"s":"aipodcast_me/index.html","t":"aipodcast_me/qr_keys.html","w":1},{"s":"aipodcast_me/index.html","t":"keeper.html","w":1},{"s":"aipodcast_me/index.html","t":"constellation.html","w":1},{"s":"aipodcast_me/index.html","t":"aipodcast_me/skill-graph.html","w":1},
    {"s":"hermes-agent","t":"claude-code","w":2},{"s":"hermes-agent","t":"opencode","w":2},{"s":"hermes-agent","t":"agentic-interpreter","w":2},
    {"s":"agentic-entrepreneurship","t":"domain-codemode","w":2},
    {"s":"cri_engine.py","t":"cri-index","w":3},{"s":"cri_server.py","t":"cri-index","w":2},{"s":"mail_agent.py","t":"mail-agent","w":3},{"s":"keeper_email.py","t":"mail-agent","w":2},{"s":"qr_key_manager.py","t":"qr-as-skill","w":3},{"s":"contract_qr.py","t":"qr-as-skill","w":3},{"s":"qr_server.py","t":"qr-as-skill","w":2},{"s":"ae_code_mode.py","t":"ae-as-skill","w":2},
]

groups = [
    {"key":"sovereign","label":"◈ SOVEREIGN SKILLS","col":"#D4AF37"},
    {"key":"fleet","label":"◈ FLEET SKILLS","col":"#00ff9d"},
    {"key":"business","label":"◈ BUSINESS SKILLS","col":"#de7a48"},
    {"key":"pages","label":"◈ PAGES (convertible)","col":"#48deac"},
    {"key":"standalone","label":"◈ STANDALONE","col":"#debe48"},
]

stats = {"declared":3,"tag":2,"mention":1}

G = {"nodes": nodes, "edges": edges, "groups": groups, "stats": stats}
G_json = json.dumps(G, ensure_ascii=False)

skill_count = sum(1 for n in nodes if n['type'] == 'skill')
page_count = sum(1 for n in nodes if n['type'] == 'page')
print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
print(f"Skills: {skill_count}, Pages: {page_count}")
print(f"JSON size: {len(G_json)} bytes")

# Write to temp file for the next step
with open("C:/æ/skill-guide/_G_json.txt", "w", encoding="utf-8") as f:
    f.write(G_json)
