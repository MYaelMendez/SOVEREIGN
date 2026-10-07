const fs = require("fs");

const core = fs.readFileSync("C:/æ/daollc-state-machine/vendor/three.core.js", "utf8");
const coreExportIdx = core.lastIndexOf("export {");
const coreBody = coreExportIdx > 0 ? core.substring(0, coreExportIdx) : core;

const moduleJs = fs.readFileSync("C:/æ/site/vendor/three.module.js", "utf8");
const modExportIdx = moduleJs.lastIndexOf("export {");
const modExportLine = moduleJs.substring(modExportIdx);
const namesMatch = modExportLine.match(/export\s*\{\s*(.*?)\s*\}\s*;/s);
const names = namesMatch ? namesMatch[1].split(",").map(n => n.trim()) : [];

console.log("Core body lines:", coreBody.split("\n").length);
console.log("Export names count:", names.length);
console.log("Sample names:", names.slice(0, 10));

const globalNames = names.map(n => `THREE.${n} = typeof ${n} !== "undefined" ? ${n} : undefined;`).join("\n");

const globalFile = `// Auto-built: single-file global THREE.js for headless Chrome\n// Source: three.core.js + three.module.js ESM bundle\n// Fix: headless Chrome does NOT execute <script type="module">\n\n${coreBody}\n\nif (typeof window === "undefined" && typeof globalThis !== "undefined") var window = globalThis;\nwindow.THREE = window.THREE || {};\n${globalNames}\n`;

fs.writeFileSync("C:/æ/site/vendor/three.global.js", globalFile);
const sz = fs.statSync("C:/æ/site/vendor/three.global.js").size;
console.log("\nWrote three.global.js:", sz, "bytes (" + (sz/1024/1024).toFixed(2) + "MB)");
