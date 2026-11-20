import pytest

from leaguelens.valuation.waivers import Candidate, UsagePoint, rank_candidates, slope


def series(*usages):
    return [UsagePoint(week=i + 1, usage=u, snap_pct=None, points=0) for i, u in enumerate(usages)]


def test_slope():
    assert slope([0.1, 0.2, 0.3]) == pytest.approx(0.1)
    assert slope([0.3, 0.2, 0.1]) == pytest.approx(-0.1)
    assert slope([0.5]) == 0
    assert slope([]) == 0


def test_rising_player_ranks_first_within_position():
    cands = [
        Candidate("riser", "WR", series(0.1, 0.25, 0.4)),
        Candidate("steady", "WR", series(0.3, 0.3, 0.3)),
        Candidate("faller", "WR", series(0.4, 0.25, 0.1)),
    ]
    ranked = rank_candidates(cands)
    assert [r.player_id for r in ranked] == ["riser", "steady", "faller"]
    assert ranked[0].latest == 0.4


def test_requires_two_active_weeks():
    cands = [Candidate("blip", "RB", series(0, 0, 0.5)), Candidate("ok", "RB", series(0, 0.2, 0.3))]
    assert [r.player_id for r in rank_candidates(cands)] == ["ok"]


def test_single_candidate_scores_zero():
    assert rank_candidates([Candidate("a", "TE", series(0.1, 0.2))])[0].score == 0
