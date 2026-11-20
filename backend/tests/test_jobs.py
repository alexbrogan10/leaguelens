import pytest
from sqlalchemy import select

from leaguelens.clients.nflverse import FixtureStatsSource
from leaguelens.jobs.refresh import refresh_players, refresh_schedule, refresh_stats
from leaguelens.models import JobRun, NflGame, Player, PlayerWeekStat
from tests.conftest import FIXTURES


@pytest.fixture
def source():
    return FixtureStatsSource(FIXTURES / "nflverse")


def test_refresh_stats_regular_season_only(container, source):
    sf = container.session_factory
    assert refresh_stats(sf, source, 2026) == 3
    with sf() as s:
        rows = {r.gsis_id: r for r in s.scalars(select(PlayerWeekStat))}
    runner = rows["00-1"]
    assert (runner.carries, runner.rush_td, runner.receptions) == (15, 1, 3)
    assert runner.team_carries == 23  # 15 + 5 + 3 for team AAA in week 1
    assert runner.fum_lost == 1
    assert runner.snap_pct == pytest.approx(0.71)
    assert rows["00-3"].target_share == 0  # "NA" parses to 0
    assert rows["00-2"].snap_pct is None
    # Re-running replaces instead of duplicating.
    assert refresh_stats(sf, source, 2026) == 3


def test_refresh_stats_missing_season_is_noop(container, source):
    assert refresh_stats(container.session_factory, source, 1999) == 0


def test_refresh_schedule(container, source):
    sf = container.session_factory
    assert refresh_schedule(sf, source, [2026]) == 5
    with sf() as s:
        assert {g.week for g in s.scalars(select(NflGame))} == {1, 2, 4, 5, 6}


def test_refresh_players_links_ids(container, sleeper, source):
    sf = container.session_factory
    assert refresh_players(sf, sleeper, source) == 4
    with sf() as s:
        players = {p.sleeper_id: p for p in s.scalars(select(Player))}
        runs = s.scalars(select(JobRun)).all()
    assert players["101"].gsis_id == "00-1"  # via ESPN id
    assert players["102"].gsis_id == "00-2"  # via name
    assert players["BUF"].gsis_id is None  # team defense
    assert "999" not in players  # offensive lineman skipped
    assert runs[-1].status == "ok"


def test_failed_job_is_recorded(container, source, tmp_path):
    from leaguelens.clients.sleeper import FixtureSleeperClient

    empty = FixtureSleeperClient(tmp_path)
    with pytest.raises(RuntimeError):
        refresh_players(container.session_factory, empty, source)
    with container.session_factory() as s:
        run = s.scalars(select(JobRun)).one()
    assert run.status == "error"


def test_team_codes_match_sleeper():
    from leaguelens.jobs.refresh import team_code

    assert team_code("LA") == "LAR"
    assert team_code("KC") == "KC"
    assert team_code("") is None
