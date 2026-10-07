#!/usr/bin/env python3
"""CRI:// Consumer Redline Index — core calculation engine.

V1 infrastructure: source registry, ingest, normalize, validate,
component calculation, explainability, release hashing.

CRI ≠ Consumer Reality
CRI ≠ Forecast
CRI ≠ Investment Advice
CRI = reproducible measurement derived from evidenced observations
"""

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
CRI_DIR = Path(r"C:\æ\cri")
RAW_DIR = CRI_DIR / "data" / "raw"
NORMALIZED_DIR = CRI_DIR / "data" / "normalized"
RELEASES_DIR = CRI_DIR / "data" / "releases"
VINTAGES_DIR = CRI_DIR / "data" / "vintages"
CONFIG_DIR = CRI_DIR / "config"

# ══════════════════════════════════════════════════════════
# SOURCE REGISTRY
# ══════════════════════════════════════════════════════════

SOURCE_REGISTRY = {
    "savings.personal_rate": {
        "indicator_id": "savings.personal_rate",
        "provider": "BEA",
        "series": "A082RC1Q027SBEA",
        "frequency": "quarterly",
        "unit": "percent",
        "direction": "inverse",  # higher savings = less pressure
        "component": "SAVINGS",
        "transform": "percentile",
        "weight": 0.14,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "cpi.all.items": {
        "indicator_id": "cpi.all_items",
        "provider": "BLS",
        "series": "CUUR0000SA0",
        "frequency": "monthly",
        "unit": "percent_yoy",
        "direction": "positive",  # higher CPI = more pressure
        "component": "ESSENTIALS",
        "transform": "percentile",
        "weight": 0.20,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "unemployment_rate": {
        "indicator_id": "unemployment_rate",
        "provider": "BLS",
        "series": "UNRATE",
        "frequency": "monthly",
        "unit": "percent",
        "direction": "positive",
        "component": "LABOR",
        "transform": "percentile",
        "weight": 0.14,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "debt_service_ratio": {
        "indicator_id": "debt_service_ratio",
        "provider": "FRED",
        "series": "DSPI",
        "frequency": "quarterly",
        "unit": "percent",
        "direction": "positive",
        "component": "DEBT",
        "transform": "percentile",
        "weight": 0.14,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "credit_utilization": {
        "indicator_id": "credit_utilization",
        "provider": "FRED",
        "series": "CUUR0000SA0",
        "frequency": "monthly",
        "unit": "percent",
        "direction": "positive",
        "component": "CREDIT",
        "transform": "percentile",
        "weight": 0.14,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "real_disposable_income": {
        "indicator_id": "real_disposable_income",
        "provider": "BEA",
        "series": "A088RC1Q027SBEA",
        "frequency": "quarterly",
        "unit": "percent_yoy",
        "direction": "inverse",  # higher income = less pressure
        "component": "INCOME",
        "transform": "percentile",
        "weight": 0.12,
        "revision_policy": "vintage",
        "enabled": True,
    },
    "liquidty_headroom": {
        "indicator_id": "liquidty_headroom",
        "provider": "FRED",
        "series": "HEADROOM",
        "frequency": "monthly",
        "unit": "percent",
        "direction": "inverse",
        "component": "LIQUIDITY",
        "transform": "percentile",
        "weight": 0.12,
        "revision_policy": "vintage",
        "enabled": True,
    },
}

# ══════════════════════════════════════════════════════════
# COMPONENT FAMILIES
# ══════════════════════════════════════════════════════════

COMPONENT_FAMILIES = {
    "ESSENTIALS": {"indicators": ["cpi.all_items"], "weight": 0.14},
    "DEBT": {"indicators": ["debt_service_ratio"], "weight": 0.14},
    "CREDIT": {"indicators": ["credit_utilization"], "weight": 0.14},
    "SAVINGS": {"indicators": ["savings.personal_rate"], "weight": 0.14},
    "INCOME": {"indicators": ["real_disposable_income"], "weight": 0.14},
    "LABOR": {"indicators": ["unemployment_rate"], "weight": 0.14},
    "LIQUIDITY": {"indicators": ["liquidty_headroom"], "weight": 0.14},
}

# ══════════════════════════════════════════════════════════
# CORE ENGINE
# ══════════════════════════════════════════════════════════

class Observation:
    """Single economic observation with full provenance."""

    def __init__(self, indicator_id: str, value: float, **kwargs):
        self.indicator_id = indicator_id
        self.value = value
        self.observation_date = kwargs.get("observation_date", "")
        self.release_date = kwargs.get("release_date", "")
        self.retrieved_at = kwargs.get("retrieved_at", datetime.now(timezone.utc).isoformat())
        self.unit = kwargs.get("unit", "")
        self.frequency = kwargs.get("frequency", "")
        self.vintage = kwargs.get("vintage", 1)
        self.source_reference = kwargs.get("source_reference", "")
        self.payload_hash = self._compute_hash()
        self.producer_hash = kwargs.get("producer_hash", "")

    def _compute_hash(self) -> str:
        """Compute hash of this observation for tamper detection."""
        data = json.dumps({
            "indicator_id": self.indicator_id,
            "value": self.value,
            "observation_date": self.observation_date,
            "release_date": self.release_date,
            "vintage": self.vintage,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "indicator_id": self.indicator_id,
            "value": self.value,
            "observation_date": self.observation_date,
            "release_date": self.release_date,
            "retrieved_at": self.retrieved_at,
            "unit": self.unit,
            "frequency": self.frequency,
            "vintage": self.vintage,
            "source_reference": self.source_reference,
            "payload_hash": self.payload_hash,
            "producer_hash": self.producer_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        obs = cls(
            indicator_id=d["indicator_id"],
            value=d["value"],
            observation_date=d.get("observation_date", ""),
            release_date=d.get("release_date", ""),
            retrieved_at=d.get("retrieved_at", ""),
            unit=d.get("unit", ""),
            frequency=d.get("frequency", ""),
            vintage=d.get("vintage", 1),
            source_reference=d.get("source_reference", ""),
            producer_hash=d.get("producer_hash", ""),
        )
        return obs


class Normalizer:
    """Transform raw series to 0-100 pressure scores."""

    @staticmethod
    def empirical_percentile(values: list[float], target: float) -> float:
        """Convert value to percentile-based pressure score 0-100.

        Uses historical empirical distribution, not normal assumption.
        """
        if not values or len(values) < 2:
            return 50.0  # neutral if insufficient data

        sorted_vals = sorted(values)
        rank = sum(1 for v in sorted_vals if v <= target)
        percentile = (rank / len(sorted_vals)) * 100
        return percentile

    @staticmethod
    def inverse_percentile(values: list[float], target: float) -> float:
        """Convert inverse indicator to percentile-based pressure score.

        For indicators where lower = more pressure (e.g., savings rate).
        """
        if not values or len(values) < 2:
            return 50.0

        sorted_vals = sorted(values)
        rank = sum(1 for v in sorted_vals if v >= target)  # reversed
        percentile = (rank / len(sorted_vals)) * 100
        return percentile

    @classmethod
    def normalize(cls, observation: Observation, history: list[float]) -> float:
        """Normalize a single observation against its history.

        Returns pressure score 0-100.
        """
        source = SOURCE_REGISTRY.get(observation.indicator_id, {})
        direction = source.get("direction", "positive")

        if direction == "inverse":
            return cls.inverse_percentile(history, observation.value)
        else:
            return cls.empirical_percentile(history, observation.value)


class ComponentCalculator:
    """Calculate component scores from normalized indicators."""

    @staticmethod
    def weighted_average(scores: dict[str, float], weights: dict[str, float]) -> float:
        """Calculate weighted average of indicator scores.

        Returns 0-100 pressure score.
        """
        if not scores:
            return 50.0

        total_weight = sum(weights.get(k, 0) for k in scores.keys())
        if total_weight == 0:
            return 50.0

        weighted_sum = sum(scores[k] * weights.get(k, 0) for k in scores.keys())
        return weighted_sum / total_weight


class CRICalculator:
    """Main CRI calculation engine.

    Computes the Consumer Redline Index from observations,
    with full provenance and reproducibility.
    """

    def __init__(self):
        self.formula_version = "cri-formula-v1"
        self.weights_version = "cri-weights-v1"

    def calculate(
        self,
        observations: list[Observation],
        history: dict[str, list[float]],
    ) -> dict:
        """Calculate CRI from observations.

        Args:
            observations: list of Observation objects
            history: dict mapping indicator_id to historical values

        Returns:
            dict with CRI score, components, coverage, freshness, status
        """
        # Normalize each observation
        normalized = {}
        for obs in observations:
            hist = history.get(obs.indicator_id, [])
            score = Normalizer.normalize(obs, hist)
            normalized[obs.indicator_id] = {
                "score": score,
                "value": obs.value,
                "observation_date": obs.observation_date,
                "payload_hash": obs.payload_hash,
            }

        # Calculate component scores
        components = {}
        for component_id, config in COMPONENT_FAMILIES.items():
            indicator_scores = {}
            indicator_weights = {}
            for ind_id in config["indicators"]:
                if ind_id in normalized:
                    indicator_scores[ind_id] = normalized[ind_id]["score"]
                    source = SOURCE_REGISTRY.get(ind_id, {})
                    indicator_weights[ind_id] = source.get("weight", 0)

            if indicator_scores:
                component_score = ComponentCalculator.weighted_average(
                    indicator_scores, indicator_weights
                )
            else:
                component_score = None  # no data for this component

            components[component_id] = {
                "score": component_score,
                "indicators": indicator_scores,
                "weight": config["weight"],
            }

        # Calculate overall CRI
        valid_components = {k: v for k, v in components.items() if v["score"] is not None}
        if valid_components:
            weights_sum = sum(v["weight"] for v in valid_components.values())
            cri_score = sum(
                v["score"] * v["weight"] for v in valid_components.values()
            ) / weights_sum if weights_sum > 0 else 50.0
        else:
            cri_score = None

        # Coverage and freshness
        total_indicators = len(SOURCE_REGISTRY)
        active_indicators = sum(1 for s in SOURCE_REGISTRY.values() if s.get("enabled", False))
        observed_indicators = len(set(obs.indicator_id for obs in observations))
        coverage = (observed_indicators / active_indicators * 100) if active_indicators > 0 else 0

        # Freshness: how recent is the latest observation
        latest_dates = [
            obs.observation_date
            for obs in observations
            if obs.observation_date
        ]
        freshness = len(latest_dates) / active_indicators * 100 if active_indicators > 0 else 0

        # Status
        if coverage >= 90:
            status = "VALID"
        elif coverage >= 70:
            status = "PARTIAL"
        else:
            status = "INSUFFICIENT"

        return {
            "cri_score": round(cri_score, 1) if cri_score is not None else None,
            "components": components,
            "coverage": round(coverage, 1),
            "freshness": round(freshness, 1),
            "status": status,
            "observation_count": len(observations),
            "formula_version": self.formula_version,
            "weights_version": self.weights_version,
        }


# ══════════════════════════════════════════════════════════
# EXPLAINABILITY ENGINE
# ══════════════════════════════════════════════════════════

class ExplainabilityEngine:
    """Decomposes CRI movements mathematically.

    Answers: Why did CRI change?
    """

    @staticmethod
    def decompose(
        previous_components: dict,
        current_components: dict,
    ) -> dict:
        """Decompose CRI change by component contribution.

        Returns contribution of each component to the total change.
        """
        previous_score = previous_components.get("cri_score", 50.0)
        current_score = current_components.get("cri_score", 50.0)
        total_change = current_score - previous_score

        contributions = {}
        for component_id in current_components.get("components", {}):
            prev_score = previous_components.get("components", {}).get(component_id, {}).get("score", 50.0)
            curr_score = current_components["components"][component_id].get("score", 50.0)
            weight = current_components["components"][component_id].get("weight", 0)

            contribution = (curr_score - prev_score) * weight
            contributions[component_id] = {
                "change": round(curr_score - prev_score, 2),
                "contribution": round(contribution, 2),
                "weight": weight,
            }

        return {
            "previous_cri": previous_score,
            "current_cri": current_score,
            "total_change": round(total_change, 2),
            "contributions": contributions,
        }

    @staticmethod
    def explain(observations: list[Observation], decomposition: dict) -> str:
        """Generate human-readable explanation of CRI movement."""
        total_change = decomposition["total_change"]
        direction = "▲" if total_change > 0 else "▼" if total_change < 0 else "─"

        lines = [
            f"CRI {decomposition['previous_cri']} → {decomposition['current_cri']} {direction} {abs(total_change)}",
            "",
            "CONTRIBUTION TO CHANGE:",
        ]

        # Sort by absolute contribution
        sorted_contribs = sorted(
            decomposition["contributions"].items(),
            key=lambda x: abs(x[1]["contribution"]),
            reverse=True,
        )

        for component_id, contrib in sorted_contribs:
            change = contrib["change"]
            contribution = contrib["contribution"]
            sign = "+" if contribution > 0 else ""
            lines.append(f"  {component_id:12s} {sign}{contribution:+.2f}  (Δ{change:+.2f})")

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# RELEASE OBJECT
# ══════════════════════════════════════════════════════════

class Release:
    """Immutable CRI release with hash chain.

    Every release is a first-class object with full provenance.
    """

    def __init__(
        self,
        cri_score: float,
        components: dict,
        coverage: float,
        freshness: float,
        status: str,
        observations: list[Observation],
        formula_version: str,
        weights_version: str,
        previous_release_hash: str = "",
    ):
        self.schema = "cri://release/v1"
        self.index = "Consumer Redline Index"
        self.version = "CRI_V1"
        self.as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.cri_score = cri_score
        self.components = components
        self.coverage = coverage
        self.freshness = freshness
        self.status = status
        self.observations = [obs.to_dict() for obs in observations]
        self.formula_version = formula_version
        self.weights_version = weights_version
        self.previous_release_hash = previous_release_hash
        self.calculation_hash = self._compute_calculation_hash()
        self.release_hash = self._compute_release_hash()

    def _compute_calculation_hash(self) -> str:
        """Hash of the calculation inputs (not the release itself)."""
        data = json.dumps({
            "cri_score": self.cri_score,
            "components": self.components,
            "coverage": self.coverage,
            "freshness": self.freshness,
            "status": self.status,
            "formula_version": self.formula_version,
            "weights_version": self.weights_version,
            "observations": self.observations,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _compute_release_hash(self) -> str:
        """Hash of the complete release (includes previous hash for chain)."""
        data = json.dumps({
            "schema": self.schema,
            "index": self.index,
            "version": self.version,
            "as_of": self.as_of,
            "cri_score": self.cri_score,
            "coverage": self.coverage,
            "freshness": self.freshness,
            "status": self.status,
            "calculation_hash": self.calculation_hash,
            "previous_release_hash": self.previous_release_hash,
            "formula_version": self.formula_version,
            "weights_version": self.weights_version,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "index": self.index,
            "version": self.version,
            "as_of": self.as_of,
            "cri_score": self.cri_score,
            "coverage": self.coverage,
            "freshness": self.freshness,
            "status": self.status,
            "components": self.components,
            "observations": self.observations,
            "formula_version": self.formula_version,
            "weights_version": self.weights_version,
            "calculation_hash": self.calculation_hash,
            "previous_release_hash": self.previous_release_hash,
            "release_hash": self.release_hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CRI:// Consumer Redline Index Engine")
    subparsers = parser.add_subparsers(dest="command")

    # calculate
    calc_parser = subparsers.add_parser("calculate", help="Calculate CRI from observations")
    calc_parser.add_argument("--observations", help="JSON file with observations")
    calc_parser.add_argument("--history", help="JSON file with history")

    # explain
    explain_parser = subparsers.add_parser("explain", help="Explain CRI decomposition")
    explain_parser.add_argument("--previous", required=True, help="Previous release JSON")
    explain_parser.add_argument("--current", required=True, help="Current release JSON")

    # release
    release_parser = subparsers.add_parser("release", help="Create a new release")
    release_parser.add_argument("--observations", required=True, help="JSON file with observations")
    release_parser.add_argument("--previous-hash", default="", help="Previous release hash")

    args = parser.parse_args()

    if args.command == "calculate":
        # Load observations and history
        if args.observations:
            with open(args.observations) as f:
                obs_data = json.load(f)
            observations = [Observation.from_dict(o) for o in obs_data]
        else:
            observations = []

        if args.history:
            with open(args.history) as f:
                history = json.load(f)
        else:
            history = {}

        calculator = CRICalculator()
        result = calculator.calculate(observations, history)
        print(json.dumps(result, indent=2))

    elif args.command == "explain":
        with open(args.previous) as f:
            previous = json.load(f)
        with open(args.current) as f:
            current = json.load(f)

        engine = ExplainabilityEngine()
        decomposition = engine.decompose(previous, current)
        explanation = engine.explain([], decomposition)
        print(explanation)

    elif args.command == "release":
        with open(args.observations) as f:
            obs_data = json.load(f)
        observations = [Observation.from_dict(o) for o in obs_data]

        # Load previous release if exists
        previous_hash = args.previous_hash
        releases_dir = Path(r"C:\æ\cri\data\releases")
        if releases_dir.exists():
            release_files = sorted(releases_dir.glob("*.json"))
            if release_files and not previous_hash:
                with open(release_files[-1]) as f:
                    prev_release = json.load(f)
                previous_hash = prev_release.get("release_hash", "")

        # Calculate CRI
        history = {}  # Would load from normalized data in production
        calculator = CRICalculator()
        calc_result = calculator.calculate(observations, history)

        # Create release
        release = Release(
            cri_score=calc_result["cri_score"],
            components=calc_result["components"],
            coverage=calc_result["coverage"],
            freshness=calc_result["freshness"],
            status=calc_result["status"],
            observations=observations,
            formula_version=calculator.formula_version,
            weights_version=calculator.weights_version,
            previous_release_hash=previous_hash,
        )

        # Save release
        releases_dir.mkdir(parents=True, exist_ok=True)
        release_file = releases_dir / f"cri_{release.as_of}.json"
        with open(release_file, 'w', encoding='utf-8') as f:
            f.write(release.to_json())

        print(release.to_json())
        print(f"\nRelease saved: {release_file}")
        print(f"Release hash: {release.release_hash}")

    else:
        parser.print_help()
