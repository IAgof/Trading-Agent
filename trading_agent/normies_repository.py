"""SQLite persistence for Normies signal rows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .normies_models import NormieSignal

SCHEMA = """
CREATE TABLE IF NOT EXISTS normies_signals (
  token_id INTEGER PRIMARY KEY CHECK (token_id BETWEEN 0 AND 9999),
  owner_address TEXT,
  type_trait TEXT,
  gender_trait TEXT,
  age_trait TEXT,
  hair_trait TEXT,
  facial_trait TEXT,
  eyes_trait TEXT,
  expression_trait TEXT,
  accessory_trait TEXT,
  pixel_count INTEGER,
  customized INTEGER,
  level INTEGER,
  action_points INTEGER,
  added_pixels INTEGER,
  removed_pixels INTEGER,
  net_pixel_change INTEGER,
  rarity_score REAL NOT NULL DEFAULT 0,
  visual_density_score REAL NOT NULL DEFAULT 0,
  canvas_activity_score REAL NOT NULL DEFAULT 0,
  holder_activity_score REAL NOT NULL DEFAULT 0,
  burn_momentum_score REAL NOT NULL DEFAULT 0,
  composite_score REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ok',
  anomaly_flags TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class NormiesRepository:
    """Repository responsible for storing and querying Normie signals."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_signal(self, signal: NormieSignal) -> None:
        self._conn.execute(
            """
            INSERT INTO normies_signals (
              token_id, owner_address, type_trait, gender_trait, age_trait,
              hair_trait, facial_trait, eyes_trait, expression_trait,
              accessory_trait, pixel_count, customized, level, action_points,
              added_pixels, removed_pixels, net_pixel_change, rarity_score,
              visual_density_score, canvas_activity_score, holder_activity_score,
              burn_momentum_score, composite_score, status, anomaly_flags, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(token_id) DO UPDATE SET
              owner_address=excluded.owner_address,
              type_trait=excluded.type_trait,
              gender_trait=excluded.gender_trait,
              age_trait=excluded.age_trait,
              hair_trait=excluded.hair_trait,
              facial_trait=excluded.facial_trait,
              eyes_trait=excluded.eyes_trait,
              expression_trait=excluded.expression_trait,
              accessory_trait=excluded.accessory_trait,
              pixel_count=excluded.pixel_count,
              customized=excluded.customized,
              level=excluded.level,
              action_points=excluded.action_points,
              added_pixels=excluded.added_pixels,
              removed_pixels=excluded.removed_pixels,
              net_pixel_change=excluded.net_pixel_change,
              rarity_score=excluded.rarity_score,
              visual_density_score=excluded.visual_density_score,
              canvas_activity_score=excluded.canvas_activity_score,
              holder_activity_score=excluded.holder_activity_score,
              burn_momentum_score=excluded.burn_momentum_score,
              composite_score=excluded.composite_score,
              status=excluded.status,
              anomaly_flags=excluded.anomaly_flags,
              updated_at=CURRENT_TIMESTAMP
            """,
            self._to_params(signal),
        )
        self._conn.commit()

    def upsert_many(self, signals: Iterable[NormieSignal]) -> None:
        for signal in signals:
            self.upsert_signal(signal)

    def get_signal(self, token_id: int) -> NormieSignal | None:
        row = self._conn.execute("SELECT * FROM normies_signals WHERE token_id = ?", (token_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_signals(self) -> list[NormieSignal]:
        rows = self._conn.execute("SELECT * FROM normies_signals ORDER BY token_id ASC").fetchall()
        return [self._from_row(row) for row in rows]

    def top_signals(self, limit: int = 25) -> list[NormieSignal]:
        rows = self._conn.execute(
            "SELECT * FROM normies_signals ORDER BY composite_score DESC, token_id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def _to_params(self, signal: NormieSignal) -> tuple[object, ...]:
        return (
            signal.token_id,
            signal.owner_address,
            signal.type_trait,
            signal.gender_trait,
            signal.age_trait,
            signal.hair_trait,
            signal.facial_trait,
            signal.eyes_trait,
            signal.expression_trait,
            signal.accessory_trait,
            signal.pixel_count,
            int(signal.customized) if signal.customized is not None else None,
            signal.level,
            signal.action_points,
            signal.added_pixels,
            signal.removed_pixels,
            signal.net_pixel_change,
            signal.rarity_score,
            signal.visual_density_score,
            signal.canvas_activity_score,
            signal.holder_activity_score,
            signal.burn_momentum_score,
            signal.composite_score,
            signal.status,
            json.dumps(signal.anomaly_flags, sort_keys=True),
        )

    def _from_row(self, row: sqlite3.Row) -> NormieSignal:
        flags = json.loads(row["anomaly_flags"] or "[]")
        return NormieSignal(
            token_id=row["token_id"],
            owner_address=row["owner_address"],
            type_trait=row["type_trait"],
            gender_trait=row["gender_trait"],
            age_trait=row["age_trait"],
            hair_trait=row["hair_trait"],
            facial_trait=row["facial_trait"],
            eyes_trait=row["eyes_trait"],
            expression_trait=row["expression_trait"],
            accessory_trait=row["accessory_trait"],
            pixel_count=row["pixel_count"],
            customized=bool(row["customized"]) if row["customized"] is not None else None,
            level=row["level"],
            action_points=row["action_points"],
            added_pixels=row["added_pixels"],
            removed_pixels=row["removed_pixels"],
            net_pixel_change=row["net_pixel_change"],
            rarity_score=row["rarity_score"],
            visual_density_score=row["visual_density_score"],
            canvas_activity_score=row["canvas_activity_score"],
            holder_activity_score=row["holder_activity_score"],
            burn_momentum_score=row["burn_momentum_score"],
            composite_score=row["composite_score"],
            status=row["status"],
            anomaly_flags=flags,
        )
