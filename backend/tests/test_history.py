from leaguelens.services.history import head_to_head
from leaguelens.services.standings import WeekScore


def test_history_follows_previous_leagues(client):
    body = client.get("/api/leagues/L1/history").json()
    assert [s["season"] for s in body["seasons"]] == ["2026", "2025"]  # stops at missing league
    past = body["seasons"][1]
    assert past["champion"]["owner_id"] == "u1"
    assert past["runner_up"]["owner_id"] == "u2"
    assert body["seasons"][0]["champion"] is None  # season in progress


def test_managers_are_keyed_by_owner_across_seasons(client):
    body = client.get("/api/leagues/L1/history").json()
    managers = {m["owner_id"]: m for m in body["managers"]}
    alice = managers["u1"]
    # 2026: 1-2 (weeks 1-3). 2025 (as roster 2): lost wk1 80-100, won wk2 110-60.
    assert (alice["wins"], alice["losses"], alice["ties"]) == (2, 3, 0)
    assert alice["championships"] == 1
    assert alice["seasons"] == 2
    assert body["managers"][0]["owner_id"] == "u1"  # titles sort first
    assert managers["u2"]["display_name"] == "Bob"  # newest name wins
    assert managers["u2"]["runner_ups"] == 1


def test_head_to_head_aggregates_seasons(client):
    body = client.get("/api/leagues/L1/history").json()
    rec = next(h for h in body["head_to_head"] if (h["owner_a"], h["owner_b"]) == ("u1", "u2"))
    assert (rec["wins"], rec["losses"]) == (1, 1)
    assert rec["points_for"] == 100 + 80
    mirror = next(h for h in body["head_to_head"] if (h["owner_a"], h["owner_b"]) == ("u2", "u1"))
    assert (mirror["wins"], mirror["losses"]) == (1, 1)


def test_head_to_head_ties_and_unpaired():
    scores = [
        WeekScore(1, 1, 1, 50),
        WeekScore(1, 2, 1, 50),
        WeekScore(1, 3, None, 99),
    ]
    out = head_to_head(scores, {1: "a", 2: "b", 3: "c"})
    assert out[("a", "b")].ties == 1
    assert ("a", "c") not in out


def test_history_unknown_league(client):
    assert client.get("/api/leagues/nope/history").status_code == 404
