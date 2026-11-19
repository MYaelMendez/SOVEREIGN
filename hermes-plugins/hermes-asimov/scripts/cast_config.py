"""cast_config.py — white-label cast configuration for hermes-asimov.

One file that makes the plugin usable by ANY operator worldwide without
editing code. The cast (actors, brand, states, policy) lives in data, not
in Python:

    resolution order:  explicit path
                    -> $HERMES_ASIMOV_CAST
                    -> <plugin_dir>/cast.json
                    -> built-in neutral default

A missing file falls back (and says so). A MALFORMED config is refused,
never repaired, never silently skipped — fail closed:

    {"ok": false, "refused": true, "reason": "..."}

Programmer errors (bad path type, non-string actor name) raise builtins;
data errors are structured refusals. A refusal is a RESULT, not an
exception to route around.

Usage:
    from cast_config import load, rebrand, is_refusal
    cfg = load()                      # CastConfig | Refusal
    cfg = load("C:/ops/acme/cast.json")
    actor = cfg.by_id("hermes-agent") # alias-resolved, case-insensitive
    rgb, yaw, pitch = cfg.state("AWAITING_APPROVAL")
    flags = cfg.voice_params("F2")    # tinyVOCA CLI flags

    python cast_config.py --show
    python cast_config.py --show --config C:/ops/acme/cast.json
    python cast_config.py --validate C:/ops/acme/cast.json

White-label proof: rebrand(config_dict, operator_name, accent, cast_labels)
returns a NEW valid config dict — new operator, new brand, new labels,
zero code edits. The original dict is never mutated.

Stdlib only. Full annotations (mypy --strict target).
Authority: HUMAN://ROOT. An address is not a permission.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
import os
import re
import sys
from collections.abc import Mapping as AbcMapping
from collections.abc import Sequence as AbcSequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import (
    Any,
    Final,
    Literal,
    Mapping,
    Sequence,
    TypeGuard,
    TypedDict,
)

__all__ = [
    "SCHEMA",
    "VOICE_BASES",
    "ENV_VAR",
    "Refusal",
    "Voice",
    "Actor",
    "State",
    "Brand",
    "CastConfig",
    "load",
    "from_dict",
    "validate",
    "rebrand",
    "is_refusal",
    "DEFAULT_CONFIG",
    "main",
]

SCHEMA: Final[str] = "hermes-asimov/cast/1"
VOICE_BASES: Final[frozenset[str]] = frozenset({"F2", "M2"})
ENV_VAR: Final[str] = "HERMES_ASIMOV_CAST"
_HEX: Final[re.Pattern[str]] = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PLUGIN_DIR: Final[Path] = Path(__file__).resolve().parent.parent

SourceKind = Literal["explicit", "env", "plugin", "builtin", "dict"]


class _RefusalOptional(TypedDict, total=False):
    errors: list[str]
    source: str


class Refusal(_RefusalOptional):
    """A structured refusal. ok is always False, refused always True."""

    ok: Literal[False]
    refused: Literal[True]
    reason: str


def is_refusal(obj: object) -> TypeGuard[Refusal]:
    """True when obj is a structured refusal (a result, not an exception)."""
    return (
        isinstance(obj, dict)
        and obj.get("ok") is False
        and obj.get("refused") is True
    )


def _refuse(
    reason: str,
    *,
    errors: Sequence[str] | None = None,
    source: str | None = None,
) -> Refusal:
    out: Refusal = {"ok": False, "refused": True, "reason": reason}
    if errors is not None:
        out["errors"] = list(errors)
    if source is not None:
        out["source"] = source
    return out


def _norm(name: str) -> str:
    """Alias normalization: case-insensitive, '-'/'_' -> space, æ -> ae."""
    s = name.casefold().replace("æ", "ae").replace("-", " ").replace("_", " ")
    return " ".join(s.split())


def _is_num(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _rgb_errors(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or len(value) != 3:
        return [f"{where} must be a list of 3 integers"]
    out: list[str] = []
    for i, component in enumerate(value):
        if not isinstance(component, int) or isinstance(component, bool):
            out.append(f"{where}[{i}] must be an integer")
        elif not 0 <= component <= 255:
            out.append(f"{where}[{i}]={component} out of range 0-255")
    return out


@dataclass(frozen=True)
class Voice:
    """tinyVOCA voice identity: base model plus prosody shaping."""

    base: str
    speed: float
    pitch_shift: float
    pitch_range: float


@dataclass(frozen=True)
class Actor:
    """One member of the cast, in declared order."""

    id: str
    label: str
    role: str
    prefix: str
    head_rgb: tuple[int, int, int]
    derived: bool
    voice: Voice


@dataclass(frozen=True)
class State:
    """A named head-light state: color plus gaze orientation."""

    rgb: tuple[int, int, int]
    yaw: float
    pitch: float


@dataclass(frozen=True)
class Brand:
    """Operator-owned surface identity. All of it is data."""

    accent: str
    void: str
    prompt: str
    title: str
    tagline: str
    font: str


@dataclass(frozen=True)
class CastConfig:
    """A validated, resolved cast configuration.

    Construct via load() or from_dict(); both fail closed on bad data.
    """

    source: str
    source_kind: SourceKind
    fallbacks: tuple[str, ...]
    raw: dict[str, Any]
    version: str
    separation_m: float
    languages: tuple[str, ...]
    policy: dict[str, Any]
    _actors: tuple[Actor, ...]
    _alias: dict[str, Actor]
    _states: dict[str, State]
    _brand: Brand
    _authority: str
    _center: Actor

    def actors(self) -> list[Actor]:
        """The cast, in declared (file) order."""
        return list(self._actors)

    def by_id(self, name: str) -> Actor | Refusal:
        """Resolve an actor by id, label, or alias.

        Case-insensitive; '-'/'_' normalize to space; 'æ' matches 'ae'.
        Accepts e.g. 'nous girl', 'hermes-agent', 'wætz', 'waetz',
        'menlo-research', 'asimov-agent', and the voice bases 'F2'/'M2'
        (first actor carrying that base, in cast order). Unknown names
        are refused, never guessed.
        """
        if not isinstance(name, str):
            raise TypeError(f"name must be str, got {type(name).__name__}")
        actor = self._alias.get(name.casefold()) or self._alias.get(_norm(name))
        if actor is None:
            return _refuse(
                f"unknown actor {name!r}; known ids: "
                + ", ".join(a.id for a in self._actors),
                source=self.source,
            )
        return actor

    def center(self) -> Actor:
        """The center actor (validated to exist at load time)."""
        return self._center

    def state(self, name: str) -> tuple[tuple[int, int, int], float, float] | Refusal:
        """(rgb, yaw, pitch) for a named state; case-insensitive."""
        if not isinstance(name, str):
            raise TypeError(f"name must be str, got {type(name).__name__}")
        st = self._states.get(name.strip().upper())
        if st is None:
            return _refuse(
                f"unknown state {name!r}; known: " + ", ".join(self._states),
                source=self.source,
            )
        return (st.rgb, st.yaw, st.pitch)

    def brand(self) -> Brand:
        """Operator brand: accent, void, prompt, title, tagline, font."""
        return self._brand

    def authority(self) -> str:
        """The authority string, e.g. HUMAN://ROOT."""
        return self._authority

    def voice_params(self, actor: str | Actor) -> dict[str, Any] | Refusal:
        """tinyVOCA CLI parameters for an actor (name/alias or Actor).

        Returns the four values plus 'cli_flags': a ready argv fragment
        for scripts/tiny_voca_voice.py (--voice/--speed/--pitch-shift/
        --pitch-range).
        """
        resolved = actor if isinstance(actor, Actor) else self.by_id(actor)
        if not isinstance(resolved, Actor):
            return resolved
        v = resolved.voice
        return {
            "voice": v.base,
            "speed": v.speed,
            "pitch_shift": v.pitch_shift,
            "pitch_range": v.pitch_range,
            "cli_flags": [
                "--voice", v.base,
                "--speed", str(v.speed),
                "--pitch-shift", str(v.pitch_shift),
                "--pitch-range", str(v.pitch_range),
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """A deep copy of the underlying config dict."""
        return copy.deepcopy(self.raw)


def validate(data: object) -> list[str]:
    """Return every schema violation found (empty list == valid).

    Checks: schema id, required keys, cast ids present and unique,
    prefixes unique, rgb triples integral and within 0-255, voice base
    in {F2, M2}, finite prosody numbers, center references a cast id,
    brand hex colors, state geometry, policy shape.
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["config must be a JSON object"]
    d: dict[str, Any] = data

    if d.get("schema") != SCHEMA:
        errs.append(f"unknown schema {d.get('schema')!r}; expected {SCHEMA!r}")
    for key in (
        "authority", "brand", "cast", "center", "states",
        "separation_m", "languages", "policy", "version",
    ):
        if key not in d:
            errs.append(f"missing required key {key!r}")

    for key in ("authority", "version"):
        if key in d and (not isinstance(d[key], str) or not d[key].strip()):
            errs.append(f"{key} must be a non-empty string")

    cast = d.get("cast")
    ids: list[str] = []
    prefixes: dict[str, int] = {}
    if not isinstance(cast, list) or not cast:
        errs.append("cast must be a non-empty list")
    else:
        for i, entry in enumerate(cast):
            where = f"cast[{i}]"
            if not isinstance(entry, dict):
                errs.append(f"{where} must be an object")
                continue
            aid = entry.get("id")
            if not isinstance(aid, str) or not aid.strip():
                errs.append(f"{where}: missing cast id")
            else:
                if aid in ids:
                    errs.append(f"{where}: duplicate cast id {aid!r}")
                ids.append(aid)
            for key in ("label", "role", "prefix"):
                value = entry.get(key)
                if not isinstance(value, str):
                    errs.append(f"{where}.{key} must be a string")
                elif key != "prefix" and not value.strip():
                    errs.append(f"{where}.{key} must be non-empty")
            prefix = entry.get("prefix")
            if isinstance(prefix, str):
                if prefix in prefixes:
                    errs.append(
                        f"{where}: duplicate prefix {prefix!r} "
                        f"(also cast[{prefixes[prefix]}])"
                    )
                else:
                    prefixes[prefix] = i
            errs.extend(_rgb_errors(entry.get("head_rgb"), f"{where}.head_rgb"))
            if not isinstance(entry.get("derived"), bool):
                errs.append(f"{where}.derived must be a boolean")
            voice = entry.get("voice")
            if not isinstance(voice, dict):
                errs.append(f"{where}.voice must be an object")
                continue
            base = voice.get("base")
            if not isinstance(base, str) or base not in VOICE_BASES:
                errs.append(
                    f"{where}.voice.base {base!r} not in {{F2, M2}}"
                )
            for key in ("speed", "pitch_shift", "pitch_range"):
                value = voice.get(key)
                if not _is_num(value):
                    errs.append(f"{where}.voice.{key} must be a number")
                elif not math.isfinite(value):
                    errs.append(f"{where}.voice.{key} must be finite")
            speed = voice.get("speed")
            if _is_num(speed) and speed <= 0:
                errs.append(f"{where}.voice.speed must be > 0")
            pitch_range = voice.get("pitch_range")
            if _is_num(pitch_range) and pitch_range <= 0:
                errs.append(f"{where}.voice.pitch_range must be > 0")

    center = d.get("center")
    if "center" in d:
        if not isinstance(center, str) or not center.strip():
            errs.append("center must be a non-empty string")
        elif ids and center not in ids:
            errs.append(f"center {center!r} is not a cast id")

    states = d.get("states")
    if not isinstance(states, dict) or not states:
        errs.append("states must be a non-empty object")
    else:
        for name, st in states.items():
            where = f"states[{name!r}]"
            if not isinstance(st, dict):
                errs.append(f"{where} must be an object")
                continue
            errs.extend(_rgb_errors(st.get("rgb"), f"{where}.rgb"))
            for key in ("yaw", "pitch"):
                if not _is_num(st.get(key)):
                    errs.append(f"{where}.{key} must be a number")

    brand = d.get("brand")
    if not isinstance(brand, dict):
        errs.append("brand must be an object")
    else:
        for key in ("accent", "void", "prompt", "title", "tagline", "font"):
            value = brand.get(key)
            if not isinstance(value, str) or not value.strip():
                errs.append(f"brand.{key} must be a non-empty string")
        for key in ("accent", "void"):
            value = brand.get(key)
            if isinstance(value, str) and not _HEX.match(value):
                errs.append(f"brand.{key} {value!r} is not #RRGGBB")

    separation = d.get("separation_m")
    if "separation_m" in d:
        if not _is_num(separation):
            errs.append("separation_m must be a number")
        elif separation <= 0:
            errs.append("separation_m must be > 0")

    languages = d.get("languages")
    if not isinstance(languages, list) or not languages:
        errs.append("languages must be a non-empty list")
    else:
        for i, lang in enumerate(languages):
            if not isinstance(lang, str) or not lang.strip():
                errs.append(f"languages[{i}] must be a non-empty string")

    policy = d.get("policy")
    if not isinstance(policy, dict):
        errs.append("policy must be an object")
    else:
        if not isinstance(policy.get("fail_closed"), bool):
            errs.append("policy.fail_closed must be a boolean")
        motion = policy.get("motion_requires")
        if not isinstance(motion, str) or not motion.strip():
            errs.append("policy.motion_requires must be a non-empty string")
        allowlist = policy.get("allowlist_cli")
        if not isinstance(allowlist, list) or not all(
            isinstance(x, str) for x in allowlist
        ):
            errs.append("policy.allowlist_cli must be a list of strings")
        if not isinstance(policy.get("rules_source"), str):
            errs.append("policy.rules_source must be a string")

    return errs


def _build(
    d: dict[str, Any],
    source: str,
    source_kind: SourceKind,
    fallbacks: tuple[str, ...],
) -> CastConfig:
    actors: list[Actor] = []
    for entry in d["cast"]:
        v = entry["voice"]
        rgb = entry["head_rgb"]
        actors.append(
            Actor(
                id=entry["id"],
                label=entry["label"],
                role=entry["role"],
                prefix=entry["prefix"],
                head_rgb=(rgb[0], rgb[1], rgb[2]),
                derived=entry["derived"],
                voice=Voice(
                    base=v["base"],
                    speed=float(v["speed"]),
                    pitch_shift=float(v["pitch_shift"]),
                    pitch_range=float(v["pitch_range"]),
                ),
            )
        )
    ordered = tuple(actors)
    alias: dict[str, Actor] = {}
    for a in ordered:
        for key in (a.id, a.label):
            alias.setdefault(key.casefold(), a)
            alias.setdefault(_norm(key), a)
    for a in ordered:  # voice-base aliases: first actor per base wins
        alias.setdefault(_norm(a.voice.base), a)
    states: dict[str, State] = {}
    for name, st in d["states"].items():
        rgb = st["rgb"]
        states[name.upper()] = State(
            rgb=(rgb[0], rgb[1], rgb[2]),
            yaw=float(st["yaw"]),
            pitch=float(st["pitch"]),
        )
    b = d["brand"]
    brand = Brand(
        accent=b["accent"],
        void=b["void"],
        prompt=b["prompt"],
        title=b["title"],
        tagline=b["tagline"],
        font=b["font"],
    )
    by_id: dict[str, Actor] = {a.id: a for a in ordered}
    return CastConfig(
        source=source,
        source_kind=source_kind,
        fallbacks=fallbacks,
        raw=copy.deepcopy(d),
        version=d["version"],
        separation_m=float(d["separation_m"]),
        languages=tuple(d["languages"]),
        policy=copy.deepcopy(d["policy"]),
        _actors=ordered,
        _alias=alias,
        _states=states,
        _brand=brand,
        _authority=d["authority"],
        _center=by_id[d["center"]],
    )


def from_dict(
    data: object,
    source: str = "<dict>",
    source_kind: SourceKind = "dict",
    fallbacks: tuple[str, ...] = (),
) -> CastConfig | Refusal:
    """Validate an in-memory config dict and build a CastConfig.

    Malformed data is a structured refusal, never an exception.
    """
    errs = validate(data)
    if errs:
        return _refuse("; ".join(errs), errors=errs, source=source)
    assert isinstance(data, dict)
    return _build(data, source, source_kind, fallbacks)


def load(path: str | os.PathLike[str] | None = None) -> CastConfig | Refusal:
    """Resolve and load the cast config. Fail closed on malformed data.

    Resolution order: explicit path -> $HERMES_ASIMOV_CAST ->
    <plugin_dir>/cast.json -> built-in default. A MISSING file falls
    back to the next source (recorded in .fallbacks); a file that
    EXISTS but is unreadable or malformed is refused outright.
    A bad path type is a programmer error and raises TypeError.
    """
    if path is not None and not isinstance(path, (str, os.PathLike)):
        raise TypeError(
            f"path must be str or os.PathLike, got {type(path).__name__}"
        )
    fallbacks: list[str] = []
    candidates: list[tuple[SourceKind, Path]] = []
    if path is not None:
        candidates.append(("explicit", Path(path)))
    env_value = os.environ.get(ENV_VAR)
    if env_value:
        candidates.append(("env", Path(env_value)))
    else:
        fallbacks.append(f"{ENV_VAR} not set")
    candidates.append(("plugin", _PLUGIN_DIR / "cast.json"))

    for kind, candidate in candidates:
        if not candidate.is_file():
            fallbacks.append(f"{kind} source not found: {candidate}")
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError as exc:
            return _refuse(
                f"cannot read {kind} config {candidate}: {exc}",
                source=str(candidate),
            )
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            return _refuse(
                f"{kind} config {candidate} is not valid JSON: {exc}",
                source=str(candidate),
            )
        return from_dict(
            data,
            source=str(candidate),
            source_kind=kind,
            fallbacks=tuple(fallbacks),
        )
    return from_dict(
        copy.deepcopy(DEFAULT_CONFIG),
        source="builtin:default",
        source_kind="builtin",
        fallbacks=tuple(fallbacks),
    )


def rebrand(
    config_dict: Mapping[str, Any],
    operator_name: str,
    accent: str,
    cast_labels: Mapping[str, str] | Sequence[str] | None = None,
) -> dict[str, Any] | Refusal:
    """White-label proof: a NEW valid config for a different operator.

    Changes brand (title/prompt/tagline/accent) and cast labels only —
    ids, prefixes, voices, states, and policy are untouched, so every
    route and alias keeps working. cast_labels maps cast id -> new
    label, or is a sequence applied in cast order. The input dict is
    never mutated. Invalid input or output is a structured refusal.
    No code edit is required anywhere in this pipeline.
    """
    if not isinstance(config_dict, AbcMapping):
        raise TypeError(
            f"config_dict must be a mapping, got {type(config_dict).__name__}"
        )
    if not isinstance(operator_name, str):
        raise TypeError("operator_name must be str")
    if not isinstance(accent, str):
        raise TypeError("accent must be str")
    if isinstance(cast_labels, str):
        raise TypeError("cast_labels must be a mapping or a sequence, not str")

    base_errors = validate(dict(config_dict))
    if base_errors:
        return _refuse(
            "source config invalid: " + "; ".join(base_errors),
            errors=base_errors,
        )
    if not operator_name.strip():
        return _refuse("operator_name must be non-empty")
    if not _HEX.match(accent):
        return _refuse(f"accent {accent!r} is not #RRGGBB")

    new: dict[str, Any] = copy.deepcopy(dict(config_dict))
    name = operator_name.strip()
    slug = _norm(name).replace(" ", "-")
    brand: dict[str, Any] = new["brand"]
    brand["title"] = name.upper()
    brand["prompt"] = f">_{slug}://"
    brand["tagline"] = f"{name.upper()} · NATIVE MUJOCO · LOCAL"
    brand["accent"] = accent

    cast: list[dict[str, Any]] = new["cast"]
    if cast_labels is not None:
        if isinstance(cast_labels, AbcMapping):
            known = {a["id"] for a in cast}
            for key, label in cast_labels.items():
                if key not in known:
                    return _refuse(f"cast_labels: unknown cast id {key!r}")
                if not isinstance(label, str) or not label.strip():
                    return _refuse(
                        f"cast_labels[{key!r}] must be a non-empty string"
                    )
            for a in cast:
                if a["id"] in cast_labels:
                    a["label"] = cast_labels[a["id"]]
        else:
            labels = list(cast_labels)
            if len(labels) != len(cast):
                return _refuse(
                    f"cast_labels: expected {len(cast)} labels, "
                    f"got {len(labels)}"
                )
            for a, label in zip(cast, labels):
                if not isinstance(label, str) or not label.strip():
                    return _refuse(
                        f"cast_labels: label for {a['id']!r} "
                        "must be a non-empty string"
                    )
                a["label"] = label

    errs = validate(new)
    if errs:
        return _refuse(
            "rebrand produced invalid config: " + "; ".join(errs), errors=errs
        )
    return new


DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "schema": SCHEMA,
    "version": "0.1.0",
    "authority": "HUMAN://ROOT",
    "brand": {
        "accent": "#D4AF37",
        "void": "#050505",
        "prompt": ">_cast://",
        "title": "HERMES CAST",
        "tagline": "WHITE-LABEL · NATIVE MUJOCO · LOCAL",
        "font": "Consolas, JetBrains Mono, monospace",
    },
    "cast": [
        {
            "id": "root",
            "label": "root voice",
            "role": "root voice",
            "prefix": "",
            "head_rgb": [212, 175, 55],
            "derived": False,
            "voice": {
                "base": "F2", "speed": 1.0,
                "pitch_shift": 0.0, "pitch_range": 1.0,
            },
        },
        {
            "id": "agent",
            "label": "agent voice",
            "role": "build voice",
            "prefix": "b_",
            "head_rgb": [0, 170, 255],
            "derived": False,
            "voice": {
                "base": "M2", "speed": 1.0,
                "pitch_shift": 0.0, "pitch_range": 1.0,
            },
        },
    ],
    "center": "root",
    "states": {
        "IDLE": {"rgb": [150, 150, 155], "yaw": 0.0, "pitch": 0.0},
        "LISTENING": {"rgb": [0, 204, 255], "yaw": 0.0, "pitch": 0.0},
        "THINKING": {"rgb": [133, 233, 252], "yaw": 0.18, "pitch": -0.04},
        "SPEAKING": {"rgb": [0, 255, 159], "yaw": 0.0, "pitch": -0.08},
        "AWAITING_APPROVAL": {
            "rgb": [212, 175, 55], "yaw": 0.38, "pitch": 0.06,
        },
        "APPROVED": {"rgb": [0, 255, 159], "yaw": 0.0, "pitch": -0.1},
        "REFUSED": {"rgb": [255, 0, 255], "yaw": -0.62, "pitch": 0.2},
        "ERROR": {"rgb": [255, 59, 71], "yaw": -0.3, "pitch": 0.24},
    },
    "separation_m": 0.42,
    "languages": ["en", "es"],
    "policy": {
        "fail_closed": True,
        "motion_requires": "human_approval_or_armed_deadman",
        "allowlist_cli": ["", "caps", "help", "status"],
        "rules_source": "ae-policy.json",
    },
}


def _show_summary(cfg: CastConfig) -> dict[str, Any]:
    return {
        "ok": True,
        "source": cfg.source,
        "source_kind": cfg.source_kind,
        "fallbacks": list(cfg.fallbacks),
        "schema": cfg.raw.get("schema"),
        "version": cfg.version,
        "authority": cfg.authority(),
        "brand": asdict(cfg.brand()),
        "center": {"id": cfg.center().id, "label": cfg.center().label},
        "separation_m": cfg.separation_m,
        "languages": list(cfg.languages),
        "policy": cfg.policy,
        "actors": [asdict(a) for a in cfg.actors()],
        "states": sorted(cfg._states),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: --show (resolved source + summary), --validate <path>."""
    parser = argparse.ArgumentParser(
        prog="cast_config",
        description="White-label cast config loader/validator "
        f"(schema {SCHEMA}). Fail closed.",
    )
    parser.add_argument(
        "--validate", metavar="PATH", default=None,
        help="validate a config file; exit 0 if valid, 1 if refused",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="print the resolved config source and a summary (default)",
    )
    parser.add_argument(
        "--config", metavar="PATH", default=None,
        help="explicit config path for --show",
    )
    args = parser.parse_args(argv)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    validate_path: str | None = args.validate
    if validate_path is not None:
        p = Path(validate_path)
        if not p.is_file():
            print(json.dumps(
                _refuse(f"config file not found: {p}", source=str(p)),
                ensure_ascii=False,
            ))
            return 1
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            print(json.dumps(
                _refuse(f"cannot read {p}: {exc}", source=str(p)),
                ensure_ascii=False,
            ))
            return 1
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            print(json.dumps(
                _refuse(f"{p} is not valid JSON: {exc}", source=str(p)),
                ensure_ascii=False,
            ))
            return 1
        errs = validate(data)
        if errs:
            print(json.dumps(
                _refuse("; ".join(errs), errors=errs, source=str(p)),
                ensure_ascii=False,
            ))
            return 1
        assert isinstance(data, dict)
        print(json.dumps(
            {
                "ok": True,
                "valid": True,
                "source": str(p),
                "schema": data.get("schema"),
                "actors": len(data.get("cast", [])),
                "states": len(data.get("states", {})),
            },
            ensure_ascii=False,
        ))
        return 0

    cfg = load(args.config)
    if not isinstance(cfg, CastConfig):
        print(json.dumps(cfg, ensure_ascii=False))
        return 1
    print(json.dumps(_show_summary(cfg), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
