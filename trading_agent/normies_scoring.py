"""Scoring functions for Normies Intelligence Agent."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from .normies_models import NormieSignal

TRAIT_FIELDS = [
    "type_trait",
    "gender_trait",
    "age_trait",
    "hair_trait",
    "facial_trait",
    "eyes_trait",
    "expression_trait",
    "accessory_trait",
]


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def score_visual_density(pixel_count: int | None) -> float:
    if pixel_count is None:
        return 0.0
    return clamp(pixel_count / 1600.0)


def score_canvas_activity(signal: NormieSignal) -> float:
    score = 0.0
    if signal.customized:
        score += 0.35
    score += clamp((signal.level or 0) / 10.0) * 0.25
    score += clamp((signal.action_points or 0) / 1000.0) * 0.20
    score += clamp(abs(signal.net_pixel_change or 0) / 400.0) * 0.20
    return clamp(score)


def score_holder_activity(owner_address: str | None) -> float:
    return 0.5 if owner_address else 0.0


def score_burn_momentum(history_stats: dict[str, object] | None) -> float:
    if not history_stats:
        return 0.0
    candidate_keys = ["burned", "burnedCount", "totalBurned", "burns", "burn_count"]
    values: list[float] = []
    for key in candidate_keys:
        value = history_stats.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return 0.0
    return clamp(math.log1p(max(values)) / math.log1p(10_000))


def apply_rarity_scores(signals: list[NormieSignal]) -> None:
    """Assign inverse-frequency rarity scores across the scanned sample."""

    total = len([signal for signal in signals if signal.status == "ok"]) or 1
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for signal in signals:
        if signal.status != "ok":
            continue
        for field in TRAIT_FIELDS:
            value = getattr(signal, field)
            if value not in {None, ""}:
                counters[field][str(value)] += 1

    for signal in signals:
        trait_scores: list[float] = []
        for field in TRAIT_FIELDS:
            value = getattr(signal, field)
            if value in {None, ""}:
                continue
            freq = counters[field][str(value)] / total
            trait_scores.append(1.0 - freq)
        signal.rarity_score = clamp(sum(trait_scores) / len(trait_scores)) if trait_scores else 0.0
        signal.composite_score = composite_score(signal)


def composite_score(signal: NormieSignal) -> float:
    return clamp(
        0.30 * signal.rarity_score
        + 0.20 * signal.visual_density_score
        + 0.20 * signal.canvas_activity_score
        + 0.15 * signal.holder_activity_score
        + 0.15 * signal.burn_momentum_score
    )
