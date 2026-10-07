// Build a single-file global THREE.js from the ESM two-file bundle
const fs = require("fs");

const core = fs.readFileSync("C:/æ/daollc-state-machine/vendor/three.core.js", "utf8");
const moduleJs = fs.readFileSync("C:/æ/site/vendor/three.module.js", "utf8");

// The core file likely has its own exports. Let's check what it looks like
console.log("=== core.js head ===");
console.log(core.substring(0, 200));
console.log("=== core.js tail ===");
console.log(core.substring(core.length - 200));
console.log("=== module.js head (import line) ===");
console.log(moduleJs.substring(0, 200));
console.log("=== module.js tail (export) ===");
console.log(moduleJs.substring(moduleJs.length - 300));
