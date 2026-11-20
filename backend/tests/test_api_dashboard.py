def test_health(client):
    body = client.get("/api/health").json()
    assert body["db"] is True


def test_state(client):
    assert client.get("/api/state").json() == {
        "season": "2026",
        "week": 4,
        "season_type": "regular",
    }


def test_user_leagues(client):
    body = client.get("/api/users/alice/leagues").json()
    assert body["user"]["display_name"] == "Alice"
    assert body["user"]["avatar_url"].endswith("/abc")
    assert [lg["league_id"] for lg in body["leagues"]] == ["L1"]


def test_unknown_user_is_404(client):
    r = client.get("/api/users/nobody/leagues")
    assert r.status_code == 404
    assert "nobody" in r.json()["detail"]


def test_unknown_league_is_404(client):
    assert client.get("/api/leagues/nope/dashboard").status_code == 404


def test_dashboard_only_counts_completed_weeks(client):
    body = client.get("/api/leagues/L1/dashboard").json()
    assert body["weeks"] == [1, 2, 3]  # week 4 is in progress
    assert body["league"]["scoring_type"] == "PPR"
    top = body["standings"][0]
    assert top["team_name"] == "Cobras"
    assert (top["wins"], top["losses"], top["ties"]) == (2, 0, 1)
    assert top["luck"] > 1
    names = {row["roster_id"]: row["team_name"] for row in body["standings"]}
    assert names[2] == "Bob"  # falls back to display name without a team name
