import pytest

from leaguelens.services.standings import WeekScore, compute_records


def scores(rows):
    return [WeekScore(week=w, roster_id=r, matchup_id=m, points=p) for w, r, m, p in rows]


SAMPLE = scores(
    [
        (1, 1, 1, 100),
        (1, 2, 1, 90),
        (1, 3, 2, 80),
        (1, 4, 2, 70),
        (2, 1, 1, 60),
        (2, 3, 1, 110),
        (2, 2, 2, 120),
        (2, 4, 2, 50),
        (3, 1, 1, 95),
        (3, 4, 1, 130),
        (3, 2, 2, 85),
        (3, 3, 2, 85),
    ]
)


def by_id(records):
    return {r.roster_id: r for r in records}


def test_actual_records_including_ties():
    r = by_id(compute_records(SAMPLE, [1, 2, 3, 4]))
    assert (r[1].wins, r[1].losses, r[1].ties) == (1, 2, 0)
    assert (r[2].wins, r[2].losses, r[2].ties) == (1, 1, 1)
    assert (r[3].wins, r[3].losses, r[3].ties) == (2, 0, 1)
    assert (r[4].wins, r[4].losses, r[4].ties) == (1, 2, 0)


def test_allplay_records():
    r = by_id(compute_records(SAMPLE, [1, 2, 3, 4]))
    assert (r[1].allplay_wins, r[1].allplay_losses, r[1].allplay_ties) == (6, 3, 0)
    assert (r[2].allplay_wins, r[2].allplay_losses, r[2].allplay_ties) == (5, 3, 1)
    assert (r[3].allplay_wins, r[3].allplay_losses, r[3].allplay_ties) == (3, 5, 1)
    assert (r[4].allplay_wins, r[4].allplay_losses, r[4].allplay_ties) == (3, 6, 0)


def test_luck_is_actual_minus_expected():
    r = by_id(compute_records(SAMPLE, [1, 2, 3, 4]))
    assert r[3].expected_wins == pytest.approx(3.5 / 9 * 3)
    assert r[3].luck == pytest.approx(2.5 - 3.5 / 9 * 3)
    # Luck sums to roughly zero across a league without median games.
    assert sum(x.luck for x in r.values()) == pytest.approx(0, abs=1e-9)


def test_points_and_ordering():
    records = compute_records(SAMPLE, [1, 2, 3, 4])
    assert [x.roster_id for x in records] == [3, 2, 1, 4]  # win%, then PF tiebreak
    r = by_id(records)
    assert r[2].points_for == 295
    assert r[1].points_against == 90 + 110 + 130
    assert [r[i].power_rank for i in (2, 1, 3, 4)] == [1, 2, 3, 4]
    assert r[2].power_score == pytest.approx(0.6 * 5.5 / 9 + 0.4)


def test_median_game_adds_a_result_per_week():
    r = by_id(compute_records(SAMPLE, [1, 2, 3, 4], median_game=True))
    # week medians: 85, 85, 90 -> T1 beats median in wk1 and wk3, loses wk2
    assert (r[1].wins, r[1].losses) == (3, 3)
    assert r[1].games == 6


def test_empty_league():
    records = compute_records([], [1, 2])
    assert all(x.wins == 0 and x.power_score == 0 for x in records)
