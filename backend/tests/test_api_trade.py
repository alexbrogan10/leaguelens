import pytest

from leaguelens.clients.nflverse import FixtureStatsSource
from leaguelens.jobs.refresh import refresh_players, refresh_schedule, refresh_stats
from tests.conftest import FIXTURES


@pytest.fixture
def loaded(container, sleeper):
    source = FixtureStatsSource(FIXTURES / "nflverse")
    sf = container.session_factory
    refresh_players(sf, sleeper, source)
    refresh_stats(sf, source, 2026)
    refresh_schedule(sf, source, [2026])
    return container


def test_rosters_need_stats(client):
    r = client.get("/api/leagues/L1/rosters")
    assert r.status_code == 503
    assert "jobs" in r.json()["detail"]


def test_rosters_with_values(loaded, client):
    body = client.get("/api/leagues/L1/rosters").json()
    assert body["weeks_remaining"] == 12  # weeks 4..15
    assert body["stats_through_week"] == 1
    team1 = body["rosters"][0]
    assert [p["player_id"] for p in team1["players"]] == ["101", "102"]
    runner = team1["players"][0]
    # 80 rush yd + 1 TD + 3 rec / 20 yd, 1 fumble in PPR
    assert runner["recent_ppg"] == pytest.approx(8 + 6 + 3 + 2 - 2)
    assert runner["games_remaining"] == 3  # schedule fixture has 3 games left for AAA
    assert team1["players"][1]["availability"] == 0.95  # Questionable


def test_trade_analysis(loaded, client):
    r = client.post(
        "/api/leagues/L1/trade/analyze",
        json={"team_a": 1, "team_b": 2, "a_gives": ["101"], "b_gives": ["103"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"fair", "team_a", "team_b"}
    assert body["team_a"]["receives"][0]["name"] == "Quinn Ball"
    assert body["team_b"]["receives"][0]["name"] == "Jay Runner"
    assert {s["slot"] for s in body["team_a"]["lineup_after"]} >= {"QB", "RB", "FLEX"}
    assert body["reasons"]


@pytest.mark.parametrize(
    "payload",
    [
        {"team_a": 1, "team_b": 1, "a_gives": ["101"], "b_gives": []},
        {"team_a": 1, "team_b": 9, "a_gives": ["101"], "b_gives": []},
        {"team_a": 1, "team_b": 2, "a_gives": ["103"], "b_gives": []},
        {"team_a": 1, "team_b": 2, "a_gives": [], "b_gives": []},
    ],
)
def test_bad_trades_are_400(loaded, client, payload):
    assert client.post("/api/leagues/L1/trade/analyze", json=payload).status_code == 400


def test_waiver_radar_excludes_rostered_players(loaded, client):
    body = client.get("/api/leagues/L1/waivers").json()
    ids = {p["player_id"] for p in body["players"]}
    assert not ids & {"101", "102", "103"}
    assert body["weeks"] == [1]


def test_waiver_radar_validates_position(loaded, client):
    assert client.get("/api/leagues/L1/waivers?position=K").status_code == 422


def test_waiver_radar_needs_stats(client):
    assert client.get("/api/leagues/L1/waivers").status_code == 503
