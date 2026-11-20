import pytest

from leaguelens.valuation.scoring import StatLine, fantasy_points

PPR = {
    "pass_yd": 0.04,
    "pass_td": 4,
    "pass_int": -1,
    "rush_yd": 0.1,
    "rush_td": 6,
    "rec": 1,
    "rec_yd": 0.1,
    "rec_td": 6,
    "fum_lost": -2,
}


def test_ppr_receiver():
    line = StatLine(receptions=6, rec_yd=80, rec_td=1, fum_lost=1)
    assert fantasy_points(line, PPR, "WR") == pytest.approx(6 + 8 + 6 - 2)


def test_quarterback():
    line = StatLine(pass_yd=300, pass_td=2, pass_int=1, carries=4, rush_yd=20)
    assert fantasy_points(line, PPR, "QB") == pytest.approx(12 + 8 - 1 + 2)


def test_half_ppr_and_te_premium():
    half = {**PPR, "rec": 0.5, "bonus_rec_te": 0.5}
    line = StatLine(receptions=4, rec_yd=40)
    assert fantasy_points(line, half, "WR") == pytest.approx(2 + 4)
    assert fantasy_points(line, half, "TE") == pytest.approx(4 + 4)


def test_unknown_or_missing_keys_ignored():
    assert fantasy_points(StatLine(rush_yd=100), {"rush_yd": 0.1, "def_td": 6}) == 10
    assert fantasy_points(StatLine(rush_yd=100), {}) == 0
