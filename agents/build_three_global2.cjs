// Build a single-file global THREE.js from the ESM two-file bundle
const fs = require("fs");

const core = fs.readFileSync("C:/æ/daollc-state-machine/vendor/three.core.js", "utf8");
const moduleJs = fs.readFileSync("C:/æ/site/vendor/three.module.js", "utf8");

// Inspect core structure more
const coreLines = core.split('\n');
console.log("=== core.js: last 10 lines ===");
coreLines.slice(-10).forEach((l, i) => console.log(coreLines.length - 10 + i + 1 + ": " + l.substring(0, 120)));

console.log("\n=== core.js: first 3 lines ===");
coreLines.slice(0, 3).forEach(l => console.log(l));

// Find the import line in module.js
const moduleLines = moduleJs.split('\n');
let importLine = -1;
for (let i = 0; i < moduleLines.length; i++) {
  if (moduleLines[i].startsWith("import")) { importLine = i; break; }
}
console.log("\n=== module.js: import at line", importLine, "===");
moduleLines.slice(importLine, importLine + 3).forEach(l => console.log(l.substring(0, 150)));

// Find the export line
let exportLine = -1;
for (let i = 0; i < moduleLines.length; i++) {
  if (moduleLines[i].startsWith("export {")) { exportLine = i; break; }
}
console.log("\n=== module.js: export at line", exportLine, "===");
moduleLines[exportLine].substring(0, 200);
