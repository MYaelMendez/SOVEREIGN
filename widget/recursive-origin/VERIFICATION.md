# Verification / 2026-10-21

## Executed

- Node.js v22.16.0: `node --test core.test.mjs` -- 12 tests passed.
- Chromium through Playwright in **DOM-only mode**, with local modules inlined:
  390 x 844, 1440 x 900 and 320 x 568 -- all three scenarios passed.
- Each scenario exercised alias routing, recursive parent/child navigation,
  opt-in private-context copying, executor preference, literal text rendering,
  exact-preview review and real local Blob download, invalidation after edits,
  empty persistent storage, and absence of external network requests.
- Each scenario checked that the new frame maintained a 9:16 ratio, that the
  page had no horizontal overflow, and that the underlying fixture retained
  the **same DOM object, markup and event listener** after mounting/removal.
- Repeated mount calls returned one layer. Removing and remounting discarded
  private intention. Actual rendered mobile output was visually inspected.

## Not verified

Full local HTTP navigation was attempted but blocked by the environment with
`ERR_BLOCKED_BY_ADMINISTRATOR`. No browser policy was changed. DOM-only tests
therefore inline the local import/export modules into a single script. This
exercises the implementation in a real DOM, but does **not** validate the native
module loader, HTTP response headers, CSP or deployed host integration.

No Safari/iOS device, real OpenAI Site, original WASM/Three.js runtime, connected
provider, GitHub Actions run, public deployment or signed witness was tested.
The included default HTTP test remains available for the owner's environment.

Read-back and diff checks for the GitHub commit are reported in the PR, separate
from these local checks. No production success is inferred from source checks.
