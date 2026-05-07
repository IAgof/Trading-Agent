import tempfile
from pathlib import Path

from trading_agent.normies_ingest import offline_demo_signals
from trading_agent.normies_repository import NormiesRepository
from trading_agent.normies_scoring import score_visual_density


def test_visual_density_uses_1600_pixel_canvas():
    assert score_visual_density(800) == 0.5
    assert score_visual_density(2000) == 1.0
    assert score_visual_density(None) == 0.0


def test_offline_demo_scans_and_persists_rankings():
    signals = offline_demo_signals(0, 5)
    assert len(signals) == 6
    assert all(0.0 <= signal.composite_score <= 1.0 for signal in signals)

    with tempfile.TemporaryDirectory() as tmp:
        repo = NormiesRepository(Path(tmp) / "agent.sqlite3")
        try:
            repo.upsert_many(signals)
            top = repo.top_signals(3)
            assert len(top) == 3
            assert top[0].composite_score >= top[-1].composite_score
        finally:
            repo.close()
