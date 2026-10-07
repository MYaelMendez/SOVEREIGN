// Code Mode: Build a single-file global THREE.js from ESM two-file bundle
// Runs as sandboxed Python against æ:// DSL — one execution, no round-trips
// This replaces the two-file ESM bundle (three.module.js + three.core.js)
// with a single non-module <script> that sets window.THREE

import re, json, sys, hashlib;

// Read both files from the æ filesystem
core = open("C:/æ/daollc-state-machine/vendor/three.core.js").read();
module_js = open("C:/æ/site/vendor/three.module.js").read();

// Step 1: From core.js, find the "export { ... }" line and remove it
# core.js ends with: export { ACESFilmicToneMapping, AddEquation, ... };
# This is its own export statement — we need to strip it since we'll
# inline everything into a global namespace
core_lines = core.split("\n");
core_export_line = None;
for i, line in enumerate(core_lines):
    if line.startswith("export {"):
        core_export_line = i;
        break;

if core_export_line is not None:
    core_declarations = "\n".join(core_lines[:core_export_line]);
else:
    core_declarations = core;

# Step 2: From module.js, strip the import line and convert export to global assignment
module_lines = module_js.split("\n");
# Skip first 5 lines: comment + import statement
module_body = "\n".join(module_lines[5:]);  # Skip license comment + import line

# Find and remove the "export { ... }" line in module.js
# module.js ends with: export { ACESFilmicToneMapping, ... };
mod_export_line = None;
for i, line in enumerate(module_lines):
    if line.startswith("export {"):
        mod_export_line = i;
        break;

if mod_export_line is not None:
    # Extract the export names: "export { Name1, Name2, ... };"
    export_text = module_lines[mod_export_line];
    # Extract names between { and }
    match = re.search(r'export\s*\{\s*(.*?)\s*\}\s*;', export_text);
    if match:
        names = [n.strip() for n in match.group(1).split(',')];
    else:
        names = [];  # Fallback: try to find names
else:
    names = [];

# Step 3: Build the global assignment
# Create: var THREE = { ... }; (typeof window !== 'undefined' ? window.THREE = THREE : ...)
global_assignment = """
// Single-file global THREE.js build
// Converted from ESM bundle to non-module script for headless Chrome compat
var THREE = { """ + ", ".join(names) + """ };
if (typeof window !== 'undefined') window.THREE = THREE;
if (typeof self !== 'undefined' && typeof WebGPURenderingContext !== 'undefined') self.THREE = THREE;
""" + "\n".join(core_lines[:core_export_line] if core_export_line else []) + "\n";

print("Core export line:", core_export_line);
print("Module export line:", mod_export_line);
print("Found export names:", len(names));
print("Preview names:", names[:10]);
print("Core declarations lines:", core_lines[:core_export_line] if core_export_line else len(core_lines));
print("\nModule body preview (first 200 chars):");
print(module_body[:200]);
