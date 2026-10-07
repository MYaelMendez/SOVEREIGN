// Code Mode: Fleet audit of Three.js ESM imports across all HTML scenes
// Single execution replaces ~12 sequential MCP read+grep calls
// Uses æ.storage for file I/O, æ.keeper for audit trail

import re, json, sys, os, hashlib;

// Scan all HTML files in the aipodcast_me directory for Three.js imports
const SCAN_DIR = "C:/æ/site/aipodcast_me/";
const VENDOR_DIR = "C:/æ/site/vendor/";

// Find all HTML files
const html_files = [];
for (const entry of os.listdir(SCAN_DIR)) {
  if (entry.endsWith(".html")) {
    html_files.append(SCAN_DIR + entry);
  }
}

// Pattern: detect ESM-style Three.js imports
const import_pattern = re.compile(r"""import\s+\*\s+as\s+THREE\s+from\s+['"]three['"]""");
const module_script_pattern = re.compile(r"""<script[^>]type=["']module["'][^>]*>""");

const findings = [];
for (const file_path of html_files) {
  try {
    const content = open(file_path).read();
    const has_esm_import = import_pattern.search(content);
    const has_module_script = module_script_pattern.search(content);
    const has_global_script = "three.global.js" in content;
    
    if (has_esm_import || has_module_script) {
      findings.append({
        "file": file_path.split("/")[-1],
        "path": file_path,
        file_size: len(content),
        has_esm_import: bool(has_esm_import),
        has_module_script: bool(has_module_script),
        has_global_script: has_global_script,
        import_match: has_esm_import?.group(0),
        line_number: content.split("\n").index([
          l for l in content.split("\n") if "import * as THREE" in l
        ][0]) + 1 if has_esm_import else None,
      });
    }
  } catch (e) {
    findings.append({ "file": file_path, error: str(e) });
  }
}

print(json.dumps(findings, indent=2));

// Check if three.global.js exists and has the right exports
const global_js = VENDOR_DIR + "three.global.js";
if (os.path.exists(global_js)) {
  const stat = os.stat(global_js);
  const preview = open(global_js).read(200);
  print(f"\n✅ three.global.js: {stat.st_size / 1024 / 1024:.2f} MB");
  print(f"   Starts with: {preview[:80]}...");
} else {
  print("\n❌ three.global.js NOT found at", global_js);
}

// Audit trail
æ.keeper.audit(
  "fleet_threes_audit",
  "Scan all HTML files for broken ESM imports",
  evidence=json.dumps({
    files_scanned: len(html_files),
    findings: len(findings),
    files_needing_patch: [f["file"] for f in findings if not f.get("has_global_script")]
  })
);

print(f"\nFound {len(findings)} HTML files with ESM imports");
print(f"Files needing patch: {[f['file'] for f in findings if not f.get('has_global_script')]}");
