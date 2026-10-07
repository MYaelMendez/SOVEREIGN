// Build v4: correct global THREE.js — core body (global) + module body (IIFE scope) + OrbitControls
// Fixes v3 collision: wraps module.js body in IIFE to avoid _m1$1 etc. variable name clashes
const fs = require("fs");
const path = require("path");

// ── 1. three.core.js: body (before its single export) ──
const core = fs.readFileSync("C:/æ/daollc-state-machine/vendor/three.core.js", "utf8");
const coreExportIdx = core.lastIndexOf("export {");
const coreBody = coreExportIdx > 0 ? core.substring(0, coreExportIdx) : core;

// Extract core.js export names
const coreExportText = core.substring(coreExportIdx);
const coreNamesMatch = coreExportText.match(/export\s*\{\s*([\s\S]*?)\s*\}\s*;/);
const coreNames = coreNamesMatch
  ? coreNamesMatch[1].split(",").map(n => n.trim()).filter(n => n)
  : [];
console.log("core.js: body@" + coreBody.length + " chars, export names:", coreNames.length);

// ── 2. three.module.js: body (after re-export, before final export) + final export names ──
const moduleJs = fs.readFileSync("C:/æ/site/vendor/three.module.js", "utf8");
const modLines = moduleJs.split("\n");

let modReExportLine = -1;
let modFinalExport = -1;

for (let i = 0; i < modLines.length; i++) {
  if (modLines[i].startsWith("export {") && modLines[i].includes("from '")) {
    modReExportLine = i;
  }
  if (modLines[i].startsWith("export {") && !modLines[i].includes("from '")) {
    modFinalExport = i; break;
  }
}
if (modReExportLine < 0 || modFinalExport < 0) {
  console.error("ERROR: Could not find re-export or final export in module.js");
  process.exit(1);
}

// module.js body = lines after re-export, before final export
let modBodyStart = modReExportLine + 1;
let modBodyEnd = modFinalExport;
// Skip leading/trailing blank lines
while (modBodyStart < modLines.length && modLines[modBodyStart].trim() === "") modBodyStart++;
while (modBodyEnd > modBodyStart && modLines[modBodyEnd - 1].trim() === "") modBodyEnd--;
const modBody = modLines.slice(modBodyStart, modBodyEnd).join("\n");
console.log("module.js: reExport@" + (modReExportLine+1) + " finalExport@" + (modFinalExport+1) +
  " bodyLines:" + (modBodyEnd - modBodyStart));

// Extract module.js final export names
const finalExportText = modLines[modFinalExport];
const finalNamesMatch = finalExportText.match(/export\s*\{\s*([\s\S]*?)\s*\}\s*;/);
const modNames = finalNamesMatch
  ? finalNamesMatch[1].split(",").map(n => n.trim()).filter(n => n)
  : [];
console.log("module.js final export names:", modNames.length);

// ── 3. Merge all export names (coreNames + modNames), deduped, preserve order ──
const allNames = [];
const seen = new Set();
for (const n of [...coreNames, ...modNames]) {
  if (!seen.has(n)) { seen.add(n); allNames.push(n); }
}
console.log("Merged unique export names:", allNames.length);

// Verify critical exports
const checks = ["Scene", "FogExp2", "Controls", "WebGLRenderer", "Fog",
  "PerspectiveCamera", "BufferGeometry", "OrbitControls"];
for (const check of checks) {
  console.log("  " + check + ":", allNames.includes(check) ? "✓" : "✗ MISSING FROM EXPORT LIST");
}

// ── 4. Build assignment block for core.js exports (global scope) ──
const coreAssignBlock = allNames
  .filter(n => coreNames.includes(n))
  .map(n => `THREE.${n} = typeof ${n} !== "undefined" ? ${n} : undefined;`)
  .join("\n");

// ── 5. Build assignment block for module.js exports (inside IIFE) ──
const modAssignBlock = allNames
  .filter(n => modNames.includes(n) && !coreNames.includes(n))
  .map(n => `THREE.${n} = typeof ${n} !== "undefined" ? ${n} : undefined;`)
  .join("\n");

// ── 6. OrbitControls: convert from ESM to global ──
const orbitPath = "C:/Users/yaelm/AppData/Local/hermes/cache/scratch/cdn-orbit.js";
const orbitCode = fs.readFileSync(orbitPath, "utf8");
const orbitLines = orbitCode.split("\n");

// Find import block
let orbitImportEnd = -1;
for (let i = 0; i < orbitLines.length; i++) {
  if (orbitLines[i].startsWith("import ")) {
    for (let j = i; j < orbitLines.length; j++) {
      if (orbitLines[j].includes("} from 'three'")) { orbitImportEnd = j; break; }
    }
    break;
  }
}

// Extract imported names
const orbitImportText = orbitLines.slice(0, orbitImportEnd + 1).join("\n");
const orbitImportNamesMatch = orbitImportText.match(/import\s*\{([^}]+)\}\s*from\s*'three'/s);
const orbitImportNames = orbitImportNamesMatch
  ? orbitImportNamesMatch[1].split("\n").map(n => n.trim().replace(/[,\s]+$/,"").trim()).filter(n => n)
  : [];
console.log("OrbitControls: imported names:", orbitImportNames.length);

// Find export line (last export)
let orbitExportLine = -1;
for (let i = orbitLines.length - 1; i >= 0; i--) {
  if (orbitLines[i].startsWith("export {")) { orbitExportLine = i; break; }
}
console.log("OrbitControls: export@" + (orbitExportLine + 1));

// Body = after import, before export
let orbitBodyStart = orbitImportEnd + 1;
let orbitBodyEnd = orbitExportLine;
while (orbitBodyStart < orbitLines.length && orbitLines[orbitBodyStart].trim() === "") orbitBodyStart++;
while (orbitBodyEnd > orbitBodyStart && orbitLines[orbitBodyEnd - 1].trim() === "") orbitBodyEnd--;
const orbitBody = orbitLines.slice(orbitBodyStart, orbitBodyEnd).join("\n");

const orbitSection = `// ── OrbitControls (converted from ESM: three@0.186.0/examples/jsm) ──
// Reads from global THREE, defines THREE.OrbitControls
(function() {
const { ${orbitImportNames.join(", ")} } = THREE;
${orbitBody}
THREE.OrbitControls = typeof OrbitControls !== "undefined" ? OrbitControls : undefined;
})();`;

// ── 7. Assemble the global file ──
const globalFile =
`// Auto-built: single-file global THREE.js (r186) for headless Chrome
// Source: three.core.js (global) + three.module.js (IIFE-scoped) + OrbitControls
// headless Chrome does NOT execute <script type="module">, so ESM imports are unavailable
// Build script: agents/build_global_v4.cjs

// Declare the namespace first
var THREE = {};
window.THREE = THREE;

// ── Phase 1: core.js body (defines Scene, FogExp2, Controls, Object3D, etc. as globals) ──
${coreBody}

// ── Phase 2: module.js body (defines WebGLRenderer, WebGLAnimation, setAnimationLoop, etc.) ──
// Wrapped in IIFE to avoid local-variable name collisions with core.js (_m1$1, etc.)
// References core.js classes via global scope; assigns module-only exports to THREE
(function() {
${modBody}

// Module-only export assignments (WebGLRenderer, etc.)
${modAssignBlock}
})();

// Core export assignments (Scene, FogExp2, etc.)
${coreAssignBlock}

// ── Phase 3: OrbitControls (from examples, converted to global) ──
${orbitSection}
`;

const outPath = "C:/æ/site/vendor/three.global.js";
fs.writeFileSync(outPath, globalFile);
const sz = fs.statSync(outPath).size;
console.log("\n✅ Wrote three.global.js:", sz, "bytes (" + (sz / 1024 / 1024).toFixed(2) + "MB)");

// Verify file contains key definitions
const fc = globalFile;
console.log("  class WebGLRenderer:", fc.includes("class WebGLRenderer") ? "✓" : "✗");
console.log("  setAnimationLoop:", fc.includes("setAnimationLoop") ? "✓" : "✗");
console.log("  FogExp2 class:", fc.includes("class FogExp2") ? "✓" : "✗");
console.log("  Three.js Control base class:", fc.includes("class Controls") ? "✓" : "✗");
console.log("  OrbitControls class:", fc.includes("class OrbitControls") ? "✓" : "✗");
