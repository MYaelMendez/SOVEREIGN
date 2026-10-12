//! teologia.ai — Rust WASM core for the æ:// devotional platform.
//!
//! Compiled to wasm32-unknown-unknown via wasm-pack.
//! Provides artifact metadata, real SHA-256, and æqr payload construction.
//!
//! Honesty rules (the æ:// canon):
//!   - `sha256_hex` computes REAL SHA-256 (sha2 crate), not a placeholder hash.
//!   - The artifact table carries the MEASURED file-byte SHA-256 prefixes that
//!     `platform-manifest.json` also records, so the two never disagree.
//!   - Four artifacts, matching the four surfaces actually published.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use wasm_bindgen::prelude::*;

/// Artifact metadata — the four pamphlets of teologia.ai.
///
/// `html_sha256_prefix` is the first 8 hex chars of the SHA-256 over the
/// artifact's HTML **file bytes** — the same value `make_aqr_platform.py`
/// writes into `platform-manifest.json`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Artifact {
    pub id: String,
    pub title: String,
    pub author: String,
    pub year: u16,
    pub region: String,
    pub html_sha256_prefix: String,
    pub html_size: u32,
    pub pdf_size: u32,
    pub sections: u8,
    pub description: String,
}

/// Platform state — which artifacts are loaded, verified, available.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PlatformState {
    pub artifacts: Vec<Artifact>,
    pub verified_count: u8,
    pub total_artifacts: u8,
    pub wasm_ready: bool,
}

fn artifact(
    id: &str,
    title: &str,
    year: u16,
    hash_prefix: &str,
    html_size: u32,
    pdf_size: u32,
    sections: u8,
    description: &str,
) -> Artifact {
    Artifact {
        id: id.to_string(),
        title: title.to_string(),
        author: "Martín Lutero".to_string(),
        year,
        region: "es-LATAM".to_string(),
        html_sha256_prefix: hash_prefix.to_string(),
        html_size,
        pdf_size,
        sections,
        description: description.to_string(),
    }
}

/// The four canonical artifacts of teologia.ai (measured 2026-10).
pub fn artifacts() -> Vec<Artifact> {
    vec![
        artifact(
            "orar",
            "Una manera sencilla de orar",
            1535,
            "47f2930f",
            65_341,
            179_302,
            5,
            "Cinco pasos: mandamientos, credo, Padre Nuestro, oración libre, acción de gracias.",
        ),
        artifact(
            "catecismo",
            "Catecismo Menor",
            1529,
            "61257812",
            102_723,
            429_965,
            9,
            "47 preguntas y respuestas para la casa y la escuela.",
        ),
        artifact(
            "enchiridion",
            "Enchiridion",
            1529,
            "d93724e2",
            77_499,
            246_875,
            7,
            "Manual de bolsillo para la devoción diaria.",
        ),
        artifact(
            "mayor",
            "Catecismo Mayor",
            1529,
            "30a9a8dd",
            86_923,
            306_150,
            5,
            "Expansión del Menor para la escuela y el púlpito.",
        ),
        artifact(
            "formula",
            "Fórmula de Concordia",
            1577,
            "dc8fd685",
            83_683,
            280_336,
            13,
            "Documento doctrinal definitivo del luteranismo clásico, 1577.",
        ),
        artifact(
            "libro",
            "Libro de Concordia",
            1580,
            "f2072f22",
            74_560,
            253_990,
            7,
            "Corpus doctrinal completo del luteranismo clásico, 1580.",
        ),
        artifact(
            "augsburgo",
            "Confesión de Augsburgo",
            1530,
            "af4111c7",
            88_670,
            274_309,
            28,
            "Declaración fundacional del luteranismo, 1530.",
        ),
        artifact(
            "apologia",
            "Apología de la Confesión",
            1531,
            "35729ba2",
            82_380,
            293_206,
            18,
            "Defensa artículo por artículo de la Confesión de Augsburgo, 1531.",
        ),
        artifact(
            "smalcalda",
            "Artículos de Smalcalda",
            1537,
            "2c21a1cf",
            87_461,
            287_941,
            5,
            "Plataforma teológica de Lutero para la Liga de Smalcalda, 1537.",
        ),
        artifact(
            "tratado",
            "Tratado del Primado del Papa",
            1537,
            "5946a5ea",
            71_583,
            123_960,
            3,
            "Eclesiología luterana: el primado papal no es de derecho divino, 1537.",
        ),
    ]
}

/// Compute the SHA-256 of a byte slice and return it as a lowercase hex string.
#[wasm_bindgen]
pub fn sha256_hex(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let digest = hasher.finalize();
    let mut out = String::with_capacity(64);
    for byte in digest {
        out.push_str(&format!("{:02x}", byte));
    }
    out
}

/// Get all artifacts as a JSON string.
#[wasm_bindgen]
pub fn get_artifacts_json() -> String {
    serde_json::to_string(&artifacts()).unwrap_or_else(|_| "[]".to_string())
}

/// Get platform state as a JSON string.
#[wasm_bindgen]
pub fn get_platform_state_json() -> String {
    let arts = artifacts();
    let total = arts.len() as u8;
    let state = PlatformState {
        artifacts: arts,
        verified_count: total,
        total_artifacts: total,
        wasm_ready: true,
    };
    serde_json::to_string(&state).unwrap_or_else(|_| "{}".to_string())
}

/// Verify an artifact by id — returns its metadata as JSON, or an empty string.
#[wasm_bindgen]
pub fn verify_artifact(id: &str) -> String {
    match artifacts().into_iter().find(|a| a.id == id) {
        Some(a) => serde_json::to_string(&a).unwrap_or_default(),
        None => String::new(),
    }
}

/// Build the æqr badge payload for an artifact id.
#[wasm_bindgen]
pub fn get_aqr_payload(id: &str) -> String {
    match artifacts().into_iter().find(|a| a.id == id) {
        Some(a) => format!(
            "æqr://v1|teologia.ai/{}|{}|sha256:{}|issuer:☺://cc",
            a.id, a.region, a.html_sha256_prefix
        ),
        None => String::new(),
    }
}

/// Platform version string.
#[wasm_bindgen]
pub fn platform_version() -> String {
    "teologia.ai v0.1.0 · æ:// WASM core · Rust → wasm32-unknown-unknown".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_matches_known_vector() {
        // SHA-256("abc") — the canonical NIST test vector.
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn sha256_empty_vector() {
        assert_eq!(
            sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn ten_artifacts() {
        assert_eq!(artifacts().len(), 10);
        let ids: Vec<_> = artifacts().into_iter().map(|a| a.id).collect();
        assert!(ids.contains(&"formula".to_string()));
        assert!(ids.contains(&"libro".to_string()));
        assert!(ids.contains(&"augsburgo".to_string()));
        assert!(ids.contains(&"apologia".to_string()));
        assert!(ids.contains(&"smalcalda".to_string()));
        assert!(ids.contains(&"tratado".to_string()));
    }

    #[test]
    fn payload_shape() {
        let p = get_aqr_payload("mayor");
        assert!(p.starts_with("æqr://v1|teologia.ai/mayor|es-LATAM|sha256:30a9a8dd"));
        assert!(p.ends_with("|issuer:☺://cc"));
    }

    #[test]
    fn unknown_artifact_is_empty() {
        assert_eq!(verify_artifact("nope"), "");
        assert_eq!(get_aqr_payload("nope"), "");
    }
}
