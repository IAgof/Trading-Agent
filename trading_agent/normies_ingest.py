"""Ingestion pipeline that turns Normies API responses into persisted signals."""

from __future__ import annotations

from typing import Any

from .normies_client import NormiesApiError, NormiesClient, NormiesNotAvailable
from .normies_models import TRAIT_COLUMNS, NormieSignal, attributes_from_payload, validate_token_id
from .normies_repository import NormiesRepository
from .normies_scoring import (
    apply_rarity_scores,
    score_burn_momentum,
    score_canvas_activity,
    score_holder_activity,
    score_visual_density,
)


def scan_range(
    client: NormiesClient,
    repository: NormiesRepository,
    start: int,
    end: int,
    history_stats: dict[str, object] | None = None,
) -> list[NormieSignal]:
    """Scan an inclusive token range, score it, and persist results."""

    validate_token_id(start)
    validate_token_id(end)
    if start > end:
        raise ValueError("start must be <= end")

    if history_stats is None:
        try:
            history_stats = client.get_history_stats()
        except NormiesApiError:
            history_stats = None

    signals = [ingest_one(client, token_id, history_stats) for token_id in range(start, end + 1)]
    apply_rarity_scores(signals)
    repository.upsert_many(signals)
    return signals


def ingest_one(
    client: NormiesClient,
    token_id: int,
    history_stats: dict[str, object] | None = None,
) -> NormieSignal:
    """Fetch and score one Normies token. Missing optional endpoints become flags."""

    validate_token_id(token_id)
    signal = NormieSignal(token_id=token_id)

    try:
        metadata = client.get_metadata(token_id)
    except NormiesNotAvailable:
        signal.status = "unavailable"
        signal.anomaly_flags.append("metadata_unavailable")
        return signal
    except NormiesApiError as exc:
        signal.status = "error"
        signal.anomaly_flags.append(f"metadata_error:{exc}")
        return signal

    traits_payload = _safe_fetch(signal, "traits", lambda: client.get_traits(token_id))
    pixels = _safe_fetch(signal, "pixels", lambda: client.get_pixels(token_id))
    canvas_info = _safe_fetch(signal, "canvas_info", lambda: client.get_canvas_info(token_id))
    canvas_diff = _safe_fetch(signal, "canvas_diff", lambda: client.get_canvas_diff(token_id))
    owner_payload = _safe_fetch(signal, "owner", lambda: client.get_owner(token_id))

    _apply_traits(signal, metadata)
    _apply_traits(signal, traits_payload)
    _apply_pixels(signal, pixels)
    _apply_canvas_info(signal, canvas_info)
    _apply_canvas_diff(signal, canvas_diff)
    _apply_owner(signal, owner_payload)

    signal.visual_density_score = score_visual_density(signal.pixel_count)
    signal.canvas_activity_score = score_canvas_activity(signal)
    signal.holder_activity_score = score_holder_activity(signal.owner_address)
    signal.burn_momentum_score = score_burn_momentum(history_stats)
    return signal


def offline_demo_signals(start: int, end: int) -> list[NormieSignal]:
    """Create deterministic demo rows when the public API is unreachable."""

    validate_token_id(start)
    validate_token_id(end)
    signals: list[NormieSignal] = []
    types = ["Human", "Cat", "Alien", "Agent"]
    accessories = ["None", "Beanie", "Glasses", "Laser Eyes"]
    for token_id in range(start, end + 1):
        signal = NormieSignal(
            token_id=token_id,
            owner_address=f"0x{token_id:040x}",
            type_trait=types[token_id % len(types)],
            gender_trait="Unknown",
            age_trait=str(20 + (token_id % 50)),
            hair_trait=["Buzz", "Afro", "Long", "Cap"][token_id % 4],
            facial_trait=["None", "Beard", "Mustache"][token_id % 3],
            eyes_trait=["Normal", "Shades", "Sleepy"][token_id % 3],
            expression_trait=["Smile", "Neutral", "Frown"][token_id % 3],
            accessory_trait=accessories[token_id % len(accessories)],
            pixel_count=420 + ((token_id * 37) % 360),
            customized=token_id % 5 == 0,
            level=token_id % 8,
            action_points=(token_id * 13) % 1200,
            added_pixels=(token_id * 7) % 90,
            removed_pixels=(token_id * 5) % 60,
            net_pixel_change=((token_id * 7) % 90) - ((token_id * 5) % 60),
            burn_momentum_score=0.25,
        )
        signal.visual_density_score = score_visual_density(signal.pixel_count)
        signal.canvas_activity_score = score_canvas_activity(signal)
        signal.holder_activity_score = score_holder_activity(signal.owner_address)
        signals.append(signal)
    apply_rarity_scores(signals)
    return signals


def _safe_fetch(signal: NormieSignal, label: str, fetcher: Any) -> Any:
    try:
        return fetcher()
    except NormiesNotAvailable:
        signal.anomaly_flags.append(f"{label}_unavailable")
    except NormiesApiError as exc:
        signal.anomaly_flags.append(f"{label}_error:{exc}")
    return None


def _apply_traits(signal: NormieSignal, payload: Any) -> None:
    for attr in attributes_from_payload(payload):
        raw_name = attr.get("trait_type") or attr.get("type") or attr.get("name")
        if raw_name is None:
            continue
        name = str(raw_name)
        value = attr.get("value")
        if name in TRAIT_COLUMNS:
            setattr(signal, TRAIT_COLUMNS[name], None if value is None else str(value))
        if name.lower() == "pixel count" and value is not None:
            signal.pixel_count = _to_int(value)
        if name.lower() == "level" and value is not None:
            signal.level = _to_int(value)
        if name.lower() == "action points" and value is not None:
            signal.action_points = _to_int(value)


def _apply_pixels(signal: NormieSignal, pixels: Any) -> None:
    if isinstance(pixels, str) and pixels:
        clean = "".join(ch for ch in pixels if ch in {"0", "1"})
        if clean:
            signal.pixel_count = clean.count("1")


def _apply_canvas_info(signal: NormieSignal, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    signal.customized = _first_bool(payload, ["customized", "isCustomized", "hasCanvas", "edited"])
    signal.level = _first_int(payload, ["level", "canvasLevel"], signal.level)
    signal.action_points = _first_int(payload, ["actionPoints", "action_points", "points"], signal.action_points)


def _apply_canvas_diff(signal: NormieSignal, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    signal.added_pixels = _first_int(payload, ["addedCount", "added_pixels", "added"], signal.added_pixels)
    signal.removed_pixels = _first_int(payload, ["removedCount", "removed_pixels", "removed"], signal.removed_pixels)
    if signal.added_pixels is not None or signal.removed_pixels is not None:
        signal.net_pixel_change = (signal.added_pixels or 0) - (signal.removed_pixels or 0)


def _apply_owner(signal: NormieSignal, payload: Any) -> None:
    if isinstance(payload, str):
        signal.owner_address = payload.strip() or None
    if isinstance(payload, dict):
        for key in ["owner", "owner_address", "ownerAddress", "address"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                signal.owner_address = value
                return


def _to_int(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _first_int(payload: dict[str, Any], keys: list[str], default: int | None = None) -> int | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            value = _to_int(payload[key])
            if value is not None:
                return value
    return default


def _first_bool(payload: dict[str, Any], keys: list[str]) -> bool | None:
    for key in keys:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "y"}
        if isinstance(value, (int, float)):
            return bool(value)
    return None
