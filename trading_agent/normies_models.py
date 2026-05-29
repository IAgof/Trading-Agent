"""Data models shared by ingestion, scoring, and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TRAIT_COLUMNS = {
    "Type": "type_trait",
    "Gender": "gender_trait",
    "Age": "age_trait",
    "Hair Style": "hair_trait",
    "Hair": "hair_trait",
    "Facial Hair": "facial_trait",
    "Facial": "facial_trait",
    "Eyes": "eyes_trait",
    "Expression": "expression_trait",
    "Accessory": "accessory_trait",
}


@dataclass
class NormieSignal:
    """Normalized signal row for one Normies token."""

    token_id: int
    owner_address: str | None = None
    type_trait: str | None = None
    gender_trait: str | None = None
    age_trait: str | None = None
    hair_trait: str | None = None
    facial_trait: str | None = None
    eyes_trait: str | None = None
    expression_trait: str | None = None
    accessory_trait: str | None = None
    pixel_count: int | None = None
    customized: bool | None = None
    level: int | None = None
    action_points: int | None = None
    added_pixels: int | None = None
    removed_pixels: int | None = None
    net_pixel_change: int | None = None
    rarity_score: float = 0.0
    visual_density_score: float = 0.0
    canvas_activity_score: float = 0.0
    holder_activity_score: float = 0.0
    burn_momentum_score: float = 0.0
    composite_score: float = 0.0
    status: str = "ok"
    anomaly_flags: list[str] = field(default_factory=list)

    def explanation_parts(self) -> list[str]:
        """Return human-readable reasons behind the composite score."""

        parts: list[str] = []
        if self.rarity_score >= 0.75:
            parts.append(f"rareza alta ({self.rarity_score:.2f})")
        elif self.rarity_score >= 0.45:
            parts.append(f"rareza media ({self.rarity_score:.2f})")
        if self.visual_density_score >= 0.65:
            parts.append(f"densidad visual fuerte ({self.visual_density_score:.2f})")
        if self.canvas_activity_score >= 0.40:
            parts.append(f"actividad Canvas relevante ({self.canvas_activity_score:.2f})")
        if self.holder_activity_score >= 0.50:
            parts.append("owner disponible para análisis de holder")
        if self.burn_momentum_score > 0:
            parts.append(f"momentum de burns ({self.burn_momentum_score:.2f})")
        if self.anomaly_flags:
            parts.append("flags: " + ", ".join(self.anomaly_flags))
        return parts or ["score balanceado sin una señal dominante"]


def validate_token_id(token_id: int) -> int:
    if not isinstance(token_id, int) or token_id < 0 or token_id > 9999:
        raise ValueError("token_id must be an integer between 0 and 9999")
    return token_id


def attributes_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Extract OpenSea-style attributes from several likely API response shapes."""

    if isinstance(payload, dict):
        attrs = payload.get("attributes") or payload.get("traits") or payload.get("data")
        if isinstance(attrs, list):
            return [item for item in attrs if isinstance(item, dict)]
        if isinstance(attrs, dict):
            return [{"trait_type": key, "value": value} for key, value in attrs.items()]
        return [
            {"trait_type": key, "value": value}
            for key, value in payload.items()
            if isinstance(value, (str, int, float, bool))
        ]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []
