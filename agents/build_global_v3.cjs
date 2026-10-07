// Build v3: correct global THREE.js with WebGLRenderer + setAnimationLoop + OrbitControls
// Fixes build_global_v2.cjs bugs:
//   1. Uses three.module.js body (has WebGLRenderer, WebGLAnimation, setAnimationLoop)
//   2. Merges export names from both three.core.js AND three.module.js (incl. re-export line)
//   3. Appends OrbitControls (converted from ESM to global)
const fs = require("fs");

// ── 1. three.core.js: extract body (before export) + export names ──
const core = fs.readFileSync("C:/æ/daollc-state-machine/vendor/three.core.js", "utf8");
const coreExportIdx = core.lastIndexOf("export {");
const coreBody = coreExportIdx > 0 ? core.substring(0, coreExportIdx) : core;

// Extract ALL export names from core.js (handles multi-line single export)
const coreExportText = core.substring(coreExportIdx);
const coreNamesMatch = coreExportText.match(/export\s*\{\s*([\s\S]*?)\s*\}\s*;/);
const coreNames = coreNamesMatch
  ? coreNamesMatch[1].split(",").map(n => n.trim()).filter(n => n)
  : [];
console.log("core.js export names:", coreNames.length);

// ── 2. three.module.js: extract body (after re-export, before final export) + export names ──
const moduleJs = fs.readFileSync("C:/æ/site/vendor/three.module.js", "utf8");
const modLines = moduleJs.split("\n");

let modImportLine = -1;
let modReExportLine = -1;   // "export { ... } from './three.core.js'"
let modFinalExport = -1;   // "export { ... };"  (no 'from')

for (let i = 0; i < modLines.length; i++) {
  if (modLines[i].startsWith("import ")) modImportLine = i;
  if (modLines[i].startsWith("export {") && modLines[i].includes("from '")) {
    modReExportLine = i;
  }
  if (modLines[i].startsWith("export {") && !modLines[i].includes("from '")) {
    modFinalExport = i; break;
  }
}

// Body = everything after the re-export line, before the final export
const modBody = modLines.slice(modReExportLine + 1, modFinalExport).join("\n");
console.log("module.js: import@" + (modImportLine+1) + " reExport@" + (modReExportLine+1) + " finalExport@" + (modFinalExport+1));
console.log("module.js body lines:", modLines.slice(modReExportLine + 1, modFinalExport).length);

// Export names: from the re-export line (line 7, re-exports core names) + final export
const reExportText = modLines[modReExportLine];
const reNamesMatch = reExportText.match(/export\s*\{\s*([\s\S]*?)\s*\}\s*from/);
const reNames = reNamesMatch
  ? reNamesMatch[1].split(",").map(n => n.trim()).filter(n => n)
  : [];

const finalExportText = modLines[modFinalExport];
const finalNamesMatch = finalExportText.match(/export\s*\{\s*([\s\S]*?)\s*\}\s*;/);
const finalNames = finalNamesMatch
  ? finalNamesMatch[1].split(",").map(n => n.trim()).filter(n => n)
  : [];

console.log("module.js re-export names:", reNames.length);
console.log("module.js final export names:", finalNames.length);

// ── 3. Merge all export names (deduplicated, preserve order) ──
const allNames = [];
const seen = new Set();
for (const n of [...coreNames, ...reNames, ...finalNames]) {
  if (!seen.has(n)) { seen.add(n); allNames.push(n); }
}
console.log("Merged unique export names:", allNames.length);

// Verify critical exports
for (const check of ["WebGLRenderer", "FogExp2", "Controls", "WebGPUCoordinateSystem", "Scene", "PerspectiveCamera"]) {
  console.log("  " + check + ":", allNames.includes(check) ? "✓ in export list" : "✗ MISSING");
}

// ── 4. OrbitControls: download + convert to global ──
const orbitPath = "C:/Users/yaelm/AppData/Local/hermes/cache/scratch/cdn-orbit.js";
let orbitCode = fs.readFileSync(orbitPath, "utf8");
const orbitLines = orbitCode.split("\n");

// Find import block (lines 1-12: import { ... } from 'three';)
let orbitImportEnd = -1;
for (let i = 0; i < orbitLines.length; i++) {
  if (orbitLines[i].startsWith("import ")) {
    // Find the closing }
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
console.log("OrbitControls imported names:", orbitImportNames);

// Find export line
let orbitExportLine = -1;
for (let i = orbitLines.length - 1; i >= 0; i--) {
  if (orbitLines[i].startsWith("export {")) { orbitExportLine = i; break; }
}
console.log("OrbitControls export line @" + (orbitExportLine + 1) + ":", orbitLines[orbitExportLine].trim());

// Body = everything after import, before export (strip empty lines at boundaries)
let orbitBodyStart = orbitImportEnd + 1;
let orbitBodyEnd = orbitExportLine;
// Skip leading empty lines
while (orbitBodyStart < orbitLines.length && orbitLines[orbitBodyStart].trim() === "") orbitBodyStart++;
// Skip trailing empty lines
while (orbitBodyEnd > orbitBodyStart && orbitLines[orbitBodyEnd - 1].trim() === "") orbitBodyEnd--;
const orbitBody = orbitLines.slice(orbitBodyStart, orbitBodyEnd).join("\n");

// Wrap OrbitControls in IIFE to avoid name collisions with global CORE/Controls etc.
const orbitSection = `// ── OrbitControls (converted from ESM: three@0.186.0/examples/jsm ) ──
(function() {
const { ${orbitImportNames.join(", ")} } = THREE;
${orbitBody}
THREE.OrbitControls = typeof OrbitControls !== "undefined" ? OrbitControls : undefined;
})();`;

// ── 5. Build the global file ──
const globalNames = allNames.map(n =>
  `THREE.${n} = typeof ${n} !== "undefined" ? ${n} : undefined;`
).join("\n");

const globalFile =
`// Auto-built: single-file global THREE.js for headless Chrome
// Source: three.core.js + three.module.js ESM bundle + OrbitControls
// Fix: headless Chrome does NOT execute <script type="module">
${coreBody}
${modBody}

if (typeof window === "undefined" && typeof globalThis !== "undefined") var window = globalThis;
window.THREE = window.THREE || {};
${globalNames}

${orbitSection}
`;

fs.writeFileSync("C:/æ/site/vendor/three.global.js", globalFile);
const sz = fs.statSync("C:/æ/site/vendor/three.global.js").size;
console.log("\n✅ Wrote three.global.js:", sz, "bytes (" + (sz / 1024 / 1024).toFixed(2) + "MB)");

// Verify exports are present
const checkNames = ["Scene", "FogExp2", "Controls", "WebGLRenderer", "WebGLRenderTarget", "OrbitControls"];
for (const n of checkNames) {
  const found = globalFile.includes(`THREE.${n} = typeof`);
  console.log("  THREE." + n + ":", found ? "✓ exported" : "✗ MISSING");
}
// Check setAnimationLoop presence
console.log("  setAnimationLoop:", globalFile.includes("setAnimationLoop") ? "✓ present" : "✗ MISSING");

