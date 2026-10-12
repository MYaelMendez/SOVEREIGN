#!/usr/bin/env bash
# Build the teologia.ai Rust WASM core into wasm/dist/ (a TRACKED directory,
# so the static site actually ships the binary).
#
# Root cause this script exists for: this machine has TWO Rust installs.
#   - "C:\Program Files\Rust stable MSVC 1.96"  (standalone, NO wasm32 std libs)
#   - ~/.rustup/toolchains/stable-x86_64-pc-windows-msvc  (has wasm32)
# The standalone one wins on PATH, so plain `cargo build --target wasm32-...`
# fails with "can't find crate for core/std". Worse, mixing them mid-build
# yields E0514 (crate compiled by an incompatible rustc version). Fixing the
# PATH for the whole invocation is the only reliable cure.
set -euo pipefail

TC="$HOME/.rustup/toolchains/stable-x86_64-pc-windows-msvc"
export PATH="$TC/bin:$PATH"

cd "$(dirname "$0")"

echo "== toolchain =="
rustc --version
cargo --version
rustdoc --version

echo
echo "== native tests (real SHA-256 vectors) =="
cargo test --release

echo
echo "== wasm build =="
rm -rf dist
wasm-pack build --target web --release --out-dir dist

# wasm-pack drops a `*` .gitignore inside the out dir, which would hide the
# binary from git — the exact opposite of what we want.
rm -f dist/.gitignore

echo
echo "== dist =="
ls -la dist/ | grep -vE '^total|^d'
