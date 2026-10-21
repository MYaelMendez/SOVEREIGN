# Recursive origin layer / Open Sovereign

**Build forward. Preserve backward. Return value to the human.**

An additive, removable 9:16 widget for Agentic Environments in
`MYaelMendez/SOVEREIGN`. Existing origin files, the living face, terminal,
themes, atlas, native WASM widget and publishing paths remain untouched.

## The two expressions

- Origin: `x0:y0:z0:æ:æ`.
- Public review: `x0:y0:z:0:æ:æ:æ`.

See `core.mjs` for the exact Unicode constants. These are distinct view labels,
not a conversion of the existing numeric authority axis or a new grant system.
The public label opens **review**, not deployment.

## What works

- Local origin entry aliases: `æ`, `$æ`, `$ae`, `$mcp`,
  `&mcp`, and `>_æææ://|||`.
- The heart alias opens human intention, not a separate medical agency.
- Child environments form a parent-linked tree, bounded to depth 4 / 24 nodes.
  Portrait child cards let the user enter a child and return to its parent.
- Context copying is opt-in and stays in this tab. Executor preference can be
  ae or Codex. Neither selection connects an account or activates an executor.
- Public JSON export uses an allowlist: names, lineage, references and explicit
  unconnected/unpublished states. No private intention, credentials or grants.
- Editing or adding a child invalidates the exact-record download review.
- Shadow DOM scopes styling. Mounting is idempotent for the same origin node;
  removing the layer does not reparent or replace that node or its listeners.

This module performs no fetch, storage, provider call, email, payment or filing.
ES-module files are loaded by the host; reviewed downloads create a local Blob.
It does not register an OpenAI plugin, operate a connected MCP server, synchronize
chat/Site sessions, or implement an authenticated authorization boundary.
The local checkbox is a UX review gate, not a security credential.

## Preview and test

From this directory:

```sh
node --test core.test.mjs
python3 -m http.server 4173 --bind 127.0.0.1
```

Open `http://127.0.0.1:4173/index.html`. The existing-origin area is clearly a
preservation fixture, not a copy of the real homepage. The old control must
continue counting before mounting, while mounted, and after removal.

```sh
# Requires Playwright and an installed Chromium browser.
python3 browser_test.py
# Alternative DOM-only test when local HTTP navigation is restricted:
AE_DOM_ONLY=1 python3 browser_test.py
```

`CHROMIUM_PATH` can select Chromium. `AE_TEST_OUTPUT` selects the test-output
folder. Default output is `/tmp/ae-recursive-origin-tests`, never a source folder.

## Integrate only after review

Do not replace an index file. Import from the selected host using a relative
module path, resolve its **actual existing origin element**, and opt in:

```js
import { mountBefore } from './widget/recursive-origin/widget.mjs';
const origin = document.querySelector('#your-existing-origin');
const layer = mountBefore(origin);
// Reversible: removes only the layer, leaving origin's DOM and listeners intact.
layer.destroy();
```

The module is not automatically inserted into any production page. Host layout,
CSP, modules, authentication, shared state and native widget integration still
need their own checks. On pages with absolutely positioned content, review
placement carefully; this module deliberately does not rewrite host layout.

## Continuity and publishing

Baseline inspected: `9ba31caebe5c781be03c50d069386ee4428df34d` on `master`.
All additions are confined to `widget/recursive-origin/`. Existing workflow
path filters do not target this directory. No workflow or deployment is added.
The code will be proposed on a separate branch for review, not merged to master.

Follow the repository's existing custody/pledge/dispatch/publication gates for
operational execution. Those Windows-local gates and signatures have not been
run here; source preparation is not operational execution permission.

Chat and the existing OpenAI Site remain separate operating destinations.
Neither is recreated, changed or automatically opened by this module.

**Context may propagate; authority does not.**
