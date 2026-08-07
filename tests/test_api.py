from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.pipeline import AlreadyRunningError, PipelineRunResult

UTC = timezone.utc


class FakeRecommendationRecord:
    def __init__(self, market="KRW-XRP", expected_return=0.05, n=3, hit_count=1):
        self.market = market
        self.expected_return = expected_return
        self.n = n
        self.hit_count = hit_count


def make_client():
    """No real scheduler thread, no real DB -- api.py's module-level DataStore/scheduler calls are patched."""
    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"):
        from src.api import app

        return TestClient(app)


def test_get_recommendations_returns_empty_when_never_run():
    mock_store = MagicMock()
    mock_store.get_latest_run.return_value = None

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["run_time"] is None
    assert body["recommendations"] == []


def test_get_recommendations_returns_latest_run():
    from src.data_store import PipelineRunResult as StoredRun
    from src.data_store import RecommendationRecord

    mock_store = MagicMock()
    mock_store.get_latest_run.return_value = StoredRun(
        run_time=datetime(2024, 1, 1, tzinfo=UTC),
        regime_bullish=True,
        recommendations=[RecommendationRecord("KRW-XRP", 0.05, 3, 1)],
    )

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["regime_bullish"] is True
    assert body["recommendations"][0]["market"] == "KRW-XRP"


def test_get_recommendations_includes_outcome_fields_when_evaluated():
    from src.data_store import PipelineRunResult as StoredRun
    from src.data_store import RecommendationRecord

    mock_store = MagicMock()
    mock_store.get_latest_run.return_value = StoredRun(
        run_time=datetime(2024, 1, 1, tzinfo=UTC),
        regime_bullish=True,
        recommendations=[
            RecommendationRecord(
                "KRW-XRP", 0.05, 3, 1, target_reached=True, realized_return=0.06, evaluated_at=datetime(2024, 1, 2, tzinfo=UTC)
            )
        ],
    )

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/recommendations")

    body = response.json()
    assert body["recommendations"][0]["target_reached"] is True
    assert body["recommendations"][0]["realized_return"] == 0.06
    assert body.get("history") is None


def test_get_recommendations_with_limit_returns_history():
    from src.data_store import PipelineRunResult as StoredRun
    from src.data_store import RecommendationRecord

    mock_store = MagicMock()
    mock_store.get_recent_runs.return_value = [
        StoredRun(run_time=datetime(2024, 1, 2, tzinfo=UTC), regime_bullish=True, recommendations=[RecommendationRecord("KRW-NEW", 0.05, 1, 1)]),
        StoredRun(run_time=datetime(2024, 1, 1, tzinfo=UTC), regime_bullish=True, recommendations=[RecommendationRecord("KRW-OLD", 0.05, 1, 1)]),
    ]

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/recommendations?limit=2")

    body = response.json()
    mock_store.get_recent_runs.assert_called_once_with(limit=2)
    assert body["recommendations"][0]["market"] == "KRW-NEW"  # top-level still reflects latest run
    assert [h["recommendations"][0]["market"] for h in body["history"]] == ["KRW-NEW", "KRW-OLD"]


def test_post_run_triggers_pipeline_and_returns_result():
    fake_result = PipelineRunResult(
        run_time=datetime(2024, 1, 1, tzinfo=UTC), regime_bullish=True, recommendations=[FakeRecommendationRecord()]
    )

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.run_recommendation_pipeline", return_value=fake_result) as mock_run:
        from src.api import app

        with TestClient(app) as client:
            response = client.post("/run")

    mock_run.assert_called_once()
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["market"] == "KRW-XRP"


def test_post_run_returns_409_when_already_running():
    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.run_recommendation_pipeline", side_effect=AlreadyRunningError()):
        from src.api import app

        with TestClient(app) as client:
            response = client.post("/run")

    assert response.status_code == 409


def test_health_returns_ok_when_db_reachable():
    mock_store = MagicMock()
    mock_store.ping.return_value = True

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db_connected": True}


def test_health_returns_500_when_db_unreachable():
    mock_store = MagicMock()
    mock_store.ping.side_effect = RuntimeError("db locked")

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 500
    assert response.json()["db_connected"] is False


def test_unhandled_exception_returns_generic_500_body():
    mock_store = MagicMock()
    mock_store.get_latest_run.side_effect = RuntimeError("unexpected internal detail")

    with patch("src.api.start_scheduler"), patch("src.api.stop_scheduler"), \
         patch("src.api.DataStore", return_value=mock_store):
        from src.api import app

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/recommendations")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    assert "unexpected internal detail" not in response.text
