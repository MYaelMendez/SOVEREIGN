# hermes-asimov — source mirror

This is the **versioned source** of the plugin that runs from
`%HERMES_HOME%/plugins/hermes-asimov/` and the desktop pane that runs from
`%HERMES_HOME%/desktop-plugins/hermes-asimov/`.

Those install locations are not a repo. Before this mirror existed, the 18
tools, the SimTransport, the tests and the Companion pane existed only on one
machine's disk. A reload or a wipe would have lost them.

The plugin's own `README.md` sits alongside this file; this note explains the
mirror itself.

## Install

```bash
cp -r . "$HERMES_HOME/plugins/hermes-asimov/"
cp desktop/plugin.js "$HERMES_HOME/desktop-plugins/hermes-asimov/plugin.js"
```

Then reload Hermes. `hermes plugins doctor hermes-asimov` should report
**18 tool(s)**.

## What is here

| path | role |
|---|---|
| `__init__.py` | plugin entry, 6 core tools + the system-prompt section |
| `integration.py` | front door, MoH, voice, ledger — 9 more tools |
| `render_jobs.py` | non-blocking render jobs, auto gate, receipts — 3 more |
| `scripts/sim_transport.py` | 599 lines, conforms to `menlo.asimov` Protocol |
| `scripts/asimov_protocol.py` | the 14 verbs and their policy gates |
| `scripts/moh.py` | mixture-of-harnesses routing |
| `desktop/plugin.js` | the pane, including the live **Companion** iframe |
| `tests/test_plugin.py` | 24 passing |
| `cast.json` | white-label cast definition |

## What is NOT here

**The 26 CAD meshes** (~100 MB). They are fetched from
`menloresearch/asimov-1` upstream by `agents/fetch_model.py`, hash-verified
against a manifest. Vendoring them would duplicate Menlo's repo and drift.

## The Companion pane

`desktop/plugin.js` embeds `http://127.0.0.1:8161/index.html` — the live WebGL
robot. That needs the local stack running:

```
C:\æ\agents\asimov_up.cmd
```

**Known limitation:** the iframe depends on an external local server. The clean
version serves the scene from the plugin's own static route. Not done yet.

**Unverified:** the pane parses and the Companion component is syntactically
valid, but it has never been observed rendering inside the running desktop app.

## The rule this plugin exists to enforce

Every physical action is refused until a human signs. `move()` on the companion
returns `require_approval · ACT-001, AUTH-002`. `plan stand` returns
`allowed:false, executed:false`. **An address is not a permission.**
