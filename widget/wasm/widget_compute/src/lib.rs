//! widget_compute — the reference æ:// widget's WASM computation layer.
//!
//! Deterministic, allocation-free, `extern "C"` exports. The Three.js scene
//! instantiates this module and reads its outputs to drive the mesh — so the
//! widget's *computation* is a verifiable WASM artifact (hashed in the
//! manifest), independent of the QR that points at it.
//!
//! Build: cargo build --target wasm32-unknown-unknown --release

/// Deterministic scalar field in roughly [-1, 1] — drives mesh displacement.
/// Same (x, y, t, seed) always yields the same value: the scene is reproducible.
#[no_mangle]
pub extern "C" fn wave(x: i32, y: i32, t: i32, seed: i32) -> f32 {
    let fx = x as f32 * 0.18;
    let fy = y as f32 * 0.18;
    let ft = t as f32 * 0.05;
    let s = seed as f32 * 0.001;
    (((fx + ft).sin() * (fy + s).cos()) + (((fx * fx + fy * fy) * 0.02) - ft).sin()) * 0.5
}

/// Dot product of two scalars — the trivial "capability" proof export.
#[no_mangle]
pub extern "C" fn dot(a: f32, b: f32) -> f32 {
    a * b
}

/// FNV-1a-style scramble — a deterministic per-frame id (u32).
#[no_mangle]
pub extern "C" fn hash64(seed: u32) -> u32 {
    let mut h: u32 = 2166136261 ^ seed;
    h = (h ^ (h >> 13)).wrapping_mul(16777619);
    h ^= h >> 16;
    h
}

/// The capability probe: proves the module is live and returns its constant.
#[no_mangle]
pub extern "C" fn answer() -> i32 {
    42
}
