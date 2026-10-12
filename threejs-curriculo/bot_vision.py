"""
bot_vision.py — the closed loop: perceive → reason → produce → verify.

A bot that:
  1. REASONS  — llama.cpp proposes a video scene spec from a natural request
  2. PRODUCES — the GPU renders the spec (cudavideo_spec.generate)
  3. PERCEIVES — SupervisorVideo measures the rendered video
  4. VERIFIES — PASS/FAIL + receipt; on FAIL, re-reason with the failure and retry

The loop is real: the bot's own vision gates its own generation.
"""
import os
import sys
import json
import subprocess
import tempfile

sys.path.insert(0, r"C:\æ\vision-supervision")
sys.path.insert(0, r"C:\æ\threejs-curriculo")

from vision_supervision import supervisar_video
import cudavideo_spec

LLAMA = r"C:\Users\yaelm\AppData\Local\hermes\tools\qwen2.5-coder-7b-q4_k_m.gguf"
LLAMA_CLI = r"C:\Users\yaelm\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-cli.exe"

SPEC_PROMPT = '''Output ONLY a JSON object for a video scene, no prose, no code fences.
Schema: {"title": string, "particles": integer, "palette": one of gold/cyan/neon/amber/mono, "motion": float, "duration": integer}.
Request: {request}
JSON:'''

VALID_PALETTES = {"gold", "cyan", "neon", "amber", "mono"}


def _clamp_spec(raw: dict) -> dict:
    """Force the LLM's proposal into the renderable range. The LLM is a
    proposer, not an authority: it picks the intent, we bound the values."""
    spec = {}
    spec["title"] = str(raw.get("title", "untitled"))[:48]
    try:
        spec["particles"] = max(2000, min(20000, int(raw.get("particles", 6000))))
    except (TypeError, ValueError):
        spec["particles"] = 6000
    pal = str(raw.get("palette", "gold")).lower().strip()
    spec["palette"] = pal if pal in VALID_PALETTES else "gold"
    try:
        spec["motion"] = max(0.01, min(0.08, float(raw.get("motion", 0.03))))
    except (TypeError, ValueError):
        spec["motion"] = 0.03
    try:
        spec["duration"] = max(2, min(6, int(raw.get("duration", 4))))
    except (TypeError, ValueError):
        spec["duration"] = 4
    return spec


def reason(request: str, prior_failure: str = "") -> dict:
    """Ask the local LLM to propose a scene spec."""
    prompt = SPEC_PROMPT.replace("{request}", request)
    if prior_failure:
        prompt = prompt.replace("JSON:", f"Previous attempt FAILED: {prior_failure}. Adjust. JSON:")

    try:
        out = subprocess.run(
            [LLAMA_CLI, "-m", LLAMA, "-p", prompt, "-n", "120",
             "--temp", "0.2", "--ctx-size", "4096", "-ngl", "99",
             "--color", "off", "--single-turn"],
            capture_output=True, text=True, timeout=120,
        )
        text = out.stdout
    except Exception as e:
        return {**cudavideo_spec.DEFAULT_SPEC, "_reason": f"llm error: {e}"}

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        # The prompt (with its schema braces) is echoed in stdout, so the FIRST
        # "{" is the schema, not the answer. Try every "{" from the end backward
        # and take the first that parses as a complete JSON object.
        decoder = json.JSONDecoder()
        for pos in range(text.rfind("{"), -1, -1):
            if text[pos] != "{":
                continue
            try:
                raw, _ = decoder.raw_decode(text[pos:])
                spec = _clamp_spec(raw)
                spec["_reason"] = "llm"
                spec["_raw"] = raw
                return spec
            except json.JSONDecodeError:
                continue
    return {**cudavideo_spec.DEFAULT_SPEC, "_reason": "llm-unparseable-fallback"}


def loop(request: str, out_path: str, max_attempts: int = 3) -> dict:
    """The closed loop. Returns the full trace."""
    trace = {"request": request, "attempts": []}
    failure = ""

    for attempt in range(1, max_attempts + 1):
        # 1. REASON
        spec = reason(request, failure)
        spec.setdefault("width", 720); spec.setdefault("height", 1280)
        spec.setdefault("fps", 30)

        # 2. PRODUCE
        try:
            gen = cudavideo_spec.generate(spec, out_path)
        except Exception as e:
            failure = f"render error: {e}"
            trace["attempts"].append({"attempt": attempt, "spec": spec, "error": failure})
            continue

        # 3. PERCEIVE
        report = supervisar_video(out_path, muestrear=15)

        # 4. VERIFY
        attempt_rec = {
            "attempt": attempt,
            "spec": {k: v for k, v in spec.items() if not k.startswith("_")},
            "reason": spec.get("_reason"),
            "llm_proposed": spec.get("_raw"),
            "gen": {"frames": gen["frames"], "size_mb": gen["size_mb"],
                    "capture_s": gen["capture_s"], "encode_s": gen["encode_s"]},
            "vision": {"calidad": report["calidad"], "lum": report["luminancia_media"],
                       "con": report["contraste_medio"], "mov": report["movimiento_medio"],
                       "negros": report["frames_negros"], "receipt": report["receipt"]},
        }
        trace["attempts"].append(attempt_rec)

        if report["calidad"] == "PASS":
            trace["verdict"] = "PASS"
            trace["final_receipt"] = report["receipt"]
            trace["output"] = out_path
            return trace
        else:
            failure = f"{report['calidad']}: {'; '.join(report['razones'])}"
            trace["verdict"] = "FAIL"

    trace["verdict"] = "FAIL"
    trace["output"] = out_path
    return trace


if __name__ == "__main__":
    req = sys.argv[1] if len(sys.argv) > 1 else "a calm gold particle field drifting slowly"
    out = sys.argv[2] if len(sys.argv) > 2 else "C:/æ/threejs-curriculo/bot-vision-out.mp4"
    result = loop(req, out)
    print(json.dumps(result, indent=2))
