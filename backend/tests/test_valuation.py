import pytest

from leaguelens.valuation.model import (
    DEFAULT_PARAMS,
    GameLine,
    ModelParams,
    PlayerInput,
    Projection,
    evaluate_trade,
    optimal_lineup,
    project_players,
    replacement_level,
    starters_per_position,
    trend_ratio,
    usage,
    weighted_ppg,
)
from leaguelens.valuation.scoring import StatLine

POSITIONS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN"]


def player(pid, pos, points, usages=None, remaining=7, injury=None, team="AAA"):
    """`points`/`usages` are oldest-first lists, one per week."""
    usages = usages or [0.0] * len(points)
    games = []
    for week, (pts, u) in enumerate(zip(points, usages, strict=True), start=1):
        stats = StatLine(wopr=u) if pos in ("WR", "TE") else StatLine(pass_att=u)
        if pos == "RB":
            stats = StatLine(carries=u * 100, team_carries=100)
        games.append(GameLine(week=week, points=pts, stats=stats))
    return PlayerInput(pid, pid.upper(), pos, team, games, remaining, injury)


def proj(pid, pos, ros_points, ros_value=0.0, ppg=10.0):
    return Projection(
        player_id=pid,
        name=pid,
        position=pos,
        team="AAA",
        games_played=6,
        recent_ppg=ppg,
        adjusted_ppg=ppg,
        usage_recent=None,
        usage_prior=None,
        trend_ratio=1.0,
        projected_ppg=ppg,
        replacement_ppg=5,
        vorp_ppg=max(0, ppg - 5),
        games_remaining=7,
        availability=1.0,
        ros_points=ros_points,
        ros_value=ros_value,
        injury_status=None,
    )


# --- building blocks ------------------------------------------------------------------


def test_weighted_ppg_favours_recent_games():
    assert weighted_ppg([20, 10], 0.5) == pytest.approx((20 + 5) / 1.5)
    assert weighted_ppg([], 0.85) == 0
    assert weighted_ppg([12, 12, 12], 0.85) == pytest.approx(12)


def test_trend_ratio():
    clamp = (0.75, 1.25)
    assert trend_ratio([0.3, 0.3, 0.3, 0.25, 0.25, 0.25], 3, clamp)[0] == pytest.approx(1.2)
    assert trend_ratio([0.9, 0.9, 0.9, 0.1, 0.1, 0.1], 3, clamp)[0] == 1.25  # clamped
    assert trend_ratio([0.1, 0.1, 0.1, 0.9, 0.9, 0.9], 3, clamp)[0] == 0.75
    assert trend_ratio([0.3, 0.3], 3, clamp)[0] == 1.0  # not enough games
    assert trend_ratio([0.3, 0.3, 0.3, 0, 0, 0], 3, clamp)[0] == 1.0  # no prior usage


def test_usage_by_position():
    assert usage("WR", StatLine(wopr=0.5)) == 0.5
    assert usage("TE", StatLine(target_share=0.2, air_yards_share=0.1)) == pytest.approx(0.37)
    assert usage("RB", StatLine(carries=15, team_carries=25, target_share=0.1)) == pytest.approx(
        0.8
    )
    assert usage("RB", StatLine()) == 0
    assert usage("QB", StatLine(pass_att=30, carries=5)) == 40
    assert usage("K", StatLine()) == 0


def test_starters_per_position_splits_flex():
    s = starters_per_position(POSITIONS, 10)
    assert s == {"QB": 10, "RB": 24.5, "WR": 24.5, "TE": 11}
    sf = starters_per_position(["QB", "SUPER_FLEX", "BN"], 12)
    assert sf["QB"] == pytest.approx(12 * 1.8)


def test_replacement_level():
    assert replacement_level([30, 20, 10, 5], 2) == 10
    assert replacement_level([30, 20], 5) == 20  # small pool -> last player
    assert replacement_level([], 3) == 0


# --- projections ----------------------------------------------------------------------


def test_projection_shrinks_and_applies_trend():
    pool = [player(f"wr{i}", "WR", [20 - i] * 6) for i in range(6)]
    riser = player("riser", "WR", [10] * 6, usages=[0.2, 0.2, 0.2, 0.3, 0.3, 0.3])
    params = ModelParams(decay=1.0)
    out = project_players([*pool, riser], ["WR", "BN"], 2, params)
    # 2 teams x 1 WR -> replacement is the 3rd best by PPG = 18
    assert out["riser"].replacement_ppg == 18
    adj = (6 * 10 + 2 * 18) / 8
    assert out["riser"].adjusted_ppg == pytest.approx(adj)
    assert out["riser"].trend_ratio == 1.25  # 0.3/0.2 = 1.5, clamped
    assert out["riser"].projected_ppg == pytest.approx(adj * 1.125, abs=0.01)
    assert out["wr0"].vorp_ppg == pytest.approx(out["wr0"].projected_ppg - 18, abs=0.01)
    assert out["wr5"].vorp_ppg == 0


def test_projection_ros_value_uses_games_and_injury():
    a = player("a", "RB", [20] * 6, remaining=6)
    b = player("b", "RB", [20] * 6, remaining=6, injury="IR")
    filler = player("c", "RB", [5] * 6)
    out = project_players([a, b, filler], ["RB"], 1)
    assert out["a"].availability == 1 and out["b"].availability == 0.5
    assert out["b"].ros_value == pytest.approx(out["a"].ros_value * 0.5, abs=0.1)
    assert out["a"].ros_points == pytest.approx(out["a"].projected_ppg * 6, abs=0.1)


def test_player_without_games_projects_at_replacement():
    rookie = PlayerInput("rook", "Rookie", "WR", "AAA", [], 7)
    pool = [player(f"wr{i}", "WR", [15 - i] * 4) for i in range(4)]
    out = project_players([rookie, *pool], ["WR"], 2)
    assert out["rook"].projected_ppg == out["rook"].replacement_ppg
    assert out["rook"].vorp_ppg == 0


def test_kicker_gets_flat_value():
    out = project_players([player("k", "K", [9, 9])], ["K"], 1)
    assert out["k"].projected_ppg == DEFAULT_PARAMS.flat_kdef_ppg
    assert out["k"].vorp_ppg == 0


# --- lineups and trades ---------------------------------------------------------------


def test_optimal_lineup_fills_fixed_slots_then_flex():
    roster = [
        proj("qb", "QB", 140),
        proj("rb1", "RB", 100),
        proj("rb2", "RB", 90),
        proj("rb3", "RB", 85),
        proj("wr1", "WR", 95),
        proj("wr2", "WR", 60),
        proj("te", "TE", 50),
        proj("te2", "TE", 40),
    ]
    slots, bench = optimal_lineup(roster, POSITIONS)
    assert [s.player_id for s in slots] == ["qb", "rb1", "rb2", "wr1", "wr2", "te", "rb3"]
    assert [p.player_id for p in bench] == ["te2"]


def test_optimal_lineup_leaves_empty_slots():
    slots, bench = optimal_lineup([proj("wr", "WR", 50)], ["QB", "WR", "FLEX"])
    assert [s.player_id for s in slots] == [None, "wr", None]
    assert bench == []


def team_players():
    # Team A: deep at WR, no real TE. Team B: deep at TE, weak WR2.
    ps = [
        proj("a_qb", "QB", 140),
        proj("a_rb1", "RB", 100),
        proj("a_rb2", "RB", 90),
        proj("a_wr1", "WR", 110),
        proj("a_wr2", "WR", 100),
        proj("a_wr3", "WR", 95, 30),
        proj("a_wr4", "WR", 75, 20),
        proj("a_te", "TE", 30),
        proj("b_qb", "QB", 140),
        proj("b_rb1", "RB", 100),
        proj("b_rb2", "RB", 90),
        proj("b_wr1", "WR", 110),
        proj("b_wr2", "WR", 40),
        proj("b_te1", "TE", 90, 40),
        proj("b_te2", "TE", 85, 35),
    ]
    return {p.player_id: p for p in ps}


def rosters(players):
    a = (1, [p for p in players if p.startswith("a_")])
    b = (2, [p for p in players if p.startswith("b_")])
    return a, b


POS2 = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"]


def test_trade_values_roster_fit():
    players = team_players()
    a, b = rosters(players)
    result = evaluate_trade(a, b, ["a_wr3"], ["b_te2"], players, POS2, {1: "Alpha", 2: "Beta"})
    # A: TE 30 -> 85, and WR4 (75) moves off the bench into the flex WR3 (95) leaves.
    assert result.team_a.starters_after - result.team_a.starters_before == 55 - 20
    # B: the 40-point WR2 is replaced by WR3 (95); TE2 (85) leaves the flex for WR2 (40).
    assert result.team_b.starters_after - result.team_b.starters_before == 55 - 45
    assert result.team_a.gain > 0 and result.team_b.gain > 0
    assert any("win-win" in r for r in result.reasons)
    assert any("Alpha" in r for r in result.reasons)


def test_lopsided_trade_has_a_winner():
    players = team_players()
    a, b = rosters(players)
    result = evaluate_trade(a, b, ["a_te"], ["b_wr1"], players, POS2)
    assert result.verdict == "team_a"
    assert result.team_b.gain < 0
    assert result.margin > 0


def test_identical_swap_is_fair():
    players = team_players()
    a, b = rosters(players)
    result = evaluate_trade(a, b, ["a_qb"], ["b_qb"], players, POS2)
    assert result.verdict == "fair"
    assert result.team_a.gain == 0 and result.team_b.gain == 0


def test_bench_only_player_adds_depth_note():
    players = team_players()
    players["b_rb3"] = proj("b_rb3", "RB", 20, 5)
    a, b = rosters(players)
    result = evaluate_trade(a, b, [], ["b_rb3"], players, POS2, {1: "Alpha"})
    assert any("only adds depth" in r for r in result.reasons)


def test_trade_validation():
    players = team_players()
    a, b = rosters(players)
    with pytest.raises(ValueError):
        evaluate_trade(a, b, [], [], players, POS2)
    with pytest.raises(ValueError):
        evaluate_trade(a, b, ["b_qb"], [], players, POS2)


def test_player_notes_for_trend_and_injury():
    players = team_players()
    hurt = proj("a_wr3", "WR", 95, 30)
    players["a_wr3"] = Projection(
        **{**hurt.__dict__, "trend_ratio": 1.2, "availability": 0.5, "injury_status": "IR"}
    )
    a, b = rosters(players)
    reasons = evaluate_trade(a, b, ["a_wr3"], ["b_wr2"], players, POS2).reasons
    assert any("usage is up 20%" in r for r in reasons)
    assert any("listed IR" in r for r in reasons)
