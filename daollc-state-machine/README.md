# DAOLLC.AI — living enterprise state-machine simulation

Canonical local source: `C:/æ/daollc-state-machine/index.html`.
The earlier `llm-store-preview.html` was not patched by this implementation.

This is a newly materialized prototype based on the supplied authorizeGate() snippet and the approved lifecycle/evidence specification. The complete original conversational HTML and cinematic image were not supplied; this does not claim to reproduce them verbatim.

## Run

```bash
python -m http.server 4186 --bind 127.0.0.1 --directory "C:/æ/daollc-state-machine"
```

Open `http://127.0.0.1:4186/`. Use HTTP localhost for the local ES modules, not a file:// module import.

## Components

- `original-authorizeGate.js`: historical defective snippet; not imported or executed.
- `gate.js`: independent fail-closed enterprise transition kernel, no timers. Real mode is disconnected.
- `index.html`, `app.js`: human-loop simulation, lifecycle orbit, stylized 3D buffalo economic vehicle, separate human authority marker and explicit evidence controls.
- `vendor/`: Three.js 0.186.1, MIT; package SHA-512 integrity checked before extracting the module/core/license.
- `gate.test.cjs`, `guards.test.cjs`: timer, domain separation, scope, expiry, freshness, untrusted witness, revocation, async race, replay and tuple isolation checks.
- `render.cjs`: isolated Chrome/CDP runtime, native WebMCP checks and desktop/mobile rendering. It does not modify the user's browser profile or flags.

## Verification

```bash
node --test gate.test.cjs guards.test.cjs integrity.test.cjs
node render.cjs
node render.cjs --webmcp
```

Measured: 28 gate tests passing; desktop 1440px and mobile 390px renders; no browser runtime exceptions; 700ms after authorization still not realized; compute receipt rejected for legal status; explicit valid fixture changes only the requested simulated tuple component.

Native WebMCP tested in a fresh Chrome profile with `--enable-features=WebMCP`. The measured implementation exposed `document.modelContext`, not `navigator.modelContext`. Four registered tools were discovered and `daollc_inspect_state` was invoked through the native API. This browser build required JSON-string input in executeTool; the evolving specification may differ.

Ordinary Chrome without that flag did not expose either API. The preview therefore shows unavailable rather than pretending native registration succeeded. A flag-enabled standalone browser test is not evidence that an external agent is connected to the desktop preview.

## WebMCP tool boundary

- `daollc_inspect_state`: read simulated tuple/status/journal.
- `daollc_require_evidence`: explain the domain predicate.
- `daollc_propose_transition`: select a proposal for human review; no authority grant.
- `daollc_offer_witness`: untrusted candidate evidence, only after an authorized simulation attempt; cannot verify or realize state.

No WebMCP tool authorizes, executes real external work, approves verification or realizes enterprise state. Tool schemas/hints are not the security boundary; the evidence kernel and disconnected adapters are.

## Gate

AUTHORIZE → AUTHORIZED → EXECUTE → AWAITING_EVIDENCE → WITNESS → VERIFY → SIMULATED_REALIZED.
Invalid or insufficient evidence → NOT_REALIZED. Real legal/economic/compute/physical adapters are NOT connected.

E_t=(L_t,C_t,X_t,P_t): Legal, Compute, Economic, Provenance. The kernel updates one component only after matching request, subject, domain, action, kind, outcome, freshness, fixture verifier and grant. Physical simulation requires both acknowledgment and outcome observation.

The fixture issuer is an in-memory simulator. Its results are not certificates, filings, settlements, runtime attestations or physical telemetry. Do not turn simulated values into real status labels.

## Persistence and remaining work

Tuple/journal survive successive requests within the open page, not browser restart. Export downloads a labeled simulation JSON snapshot. Durable authoritative state, authentication, trusted adapter implementations, cryptographic provenance, encrypted local storage, event replay and device enrollment are future work. The UI/kernel alone is not a deployed DAO LLC, production legal system, payment service or GPU control plane.

Do not deploy public arbitrary execution or expose local secrets. Host consolidation and production DNS/TLS remain separate tasks.

## Reference sources

- https://webmachinelearning.github.io/webmcp/ (current specification)
- https://developer.chrome.com/docs/ai/webmcp (experimental Chrome flag)
- https://raw.githubusercontent.com/chromium/chromium/main/chrome/browser/about_flags.cc (flag maps to kWebMCP)
- https://threejs.org/docs/
- https://registry.npmjs.org/three/0.186.1

Harness the storm. Preserve the principal. Build what survives. ↺
