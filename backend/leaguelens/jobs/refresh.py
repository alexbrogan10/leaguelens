"""Data refresh jobs. These run outside the API process (CLI or the worker service)."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from leaguelens.clients.nflverse import Row, StatsSource
from leaguelens.clients.sleeper import SleeperClient
from leaguelens.ids import IdLinker, pfr_to_gsis
from leaguelens.models import JobRun, NflGame, Player, PlayerWeekStat

log = logging.getLogger(__name__)

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

# nflverse column -> PlayerWeekStat attribute
STAT_COLUMNS = {
    "attempts": "pass_att",
    "completions": "pass_cmp",
    "passing_yards": "pass_yd",
    "passing_tds": "pass_td",
    "passing_interceptions": "pass_int",
    "passing_2pt_conversions": "pass_2pt",
    "carries": "carries",
    "rushing_yards": "rush_yd",
    "rushing_tds": "rush_td",
    "rushing_2pt_conversions": "rush_2pt",
    "targets": "targets",
    "receptions": "receptions",
    "receiving_yards": "rec_yd",
    "receiving_tds": "rec_td",
    "receiving_2pt_conversions": "rec_2pt",
    "receiving_air_yards": "air_yards",
    "target_share": "target_share",
    "air_yards_share": "air_yards_share",
    "wopr": "wopr",
}
FUMBLE_COLUMNS = ("rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost")


def _num(value: str | None) -> float:
    if value in (None, "", "NA"):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _run_job(
    sf: sessionmaker[Session], job: str, season: int | None, fn: Callable[[Session], int]
) -> int:
    started = datetime.now(UTC)
    with sf() as s:
        try:
            rows = fn(s)
            s.add(
                JobRun(
                    job=job,
                    season=season,
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    status="ok",
                    rows=rows,
                )
            )
            s.commit()
            log.info("%s (season=%s): %d rows", job, season, rows)
            return rows
        except Exception as exc:
            s.rollback()
            s.add(
                JobRun(
                    job=job,
                    season=season,
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    status="error",
                    message=str(exc)[:2000],
                )
            )
            s.commit()
            raise


def refresh_players(sf: sessionmaker[Session], sleeper: SleeperClient, source: StatsSource) -> int:
    def run(s: Session) -> int:
        players = sleeper.get_players()
        if not players:
            raise RuntimeError("Sleeper returned no players; keeping existing data")
        linker = IdLinker(source.players())
        now = datetime.now(UTC)
        s.execute(delete(Player))
        count = 0
        for pid, p in players.items():
            if p.get("position") not in FANTASY_POSITIONS:
                continue
            name = p.get("full_name") or " ".join(
                x for x in (p.get("first_name"), p.get("last_name")) if x
            )
            s.add(
                Player(
                    sleeper_id=str(pid),
                    gsis_id=linker.gsis_for(p) if p.get("position") != "DEF" else None,
                    full_name=name or str(pid),
                    position=p.get("position"),
                    fantasy_positions=p.get("fantasy_positions"),
                    team=p.get("team"),
                    status=p.get("status"),
                    injury_status=p.get("injury_status"),
                    age=p.get("age"),
                    years_exp=p.get("years_exp"),
                    updated_at=now,
                )
            )
            count += 1
        return count

    return _run_job(sf, "refresh_players", None, run)


def build_stat_rows(
    stats: list[Row], snaps: list[Row], pfr_map: dict[str, str], season: int
) -> list[PlayerWeekStat]:
    """Turn raw nflverse rows into ``PlayerWeekStat`` objects (regular season only)."""
    reg = [r for r in stats if r.get("season_type", "REG") == "REG" and r.get("player_id")]

    team_carries: dict[tuple[str, int], float] = defaultdict(float)
    for r in reg:
        team_carries[(r.get("team") or "", int(r["week"]))] += _num(r.get("carries"))

    snap_pct: dict[tuple[str, int], float] = {}
    for r in snaps:
        if r.get("game_type", "REG") != "REG":
            continue
        gsis = pfr_map.get(r.get("pfr_player_id") or "")
        if gsis:
            snap_pct[(gsis, int(r["week"]))] = _num(r.get("offense_pct"))

    out: list[PlayerWeekStat] = []
    for r in reg:
        week = int(r["week"])
        gsis = r["player_id"]
        values = {attr: _num(r.get(col)) for col, attr in STAT_COLUMNS.items()}
        out.append(
            PlayerWeekStat(
                gsis_id=gsis,
                season=season,
                week=week,
                name=r.get("player_display_name") or r.get("player_name") or gsis,
                team=r.get("team") or None,
                position=r.get("position") or None,
                fum_lost=sum(_num(r.get(c)) for c in FUMBLE_COLUMNS),
                team_carries=team_carries[(r.get("team") or "", week)],
                snap_pct=snap_pct.get((gsis, week)),
                **values,
            )
        )
    return out


def refresh_stats(sf: sessionmaker[Session], source: StatsSource, season: int) -> int:
    def run(s: Session) -> int:
        stats = source.weekly_player_stats(season)
        if not stats:
            return 0
        rows = build_stat_rows(
            stats, source.snap_counts(season), pfr_to_gsis(source.players()), season
        )
        s.execute(delete(PlayerWeekStat).where(PlayerWeekStat.season == season))
        s.add_all(rows)
        return len(rows)

    return _run_job(sf, "refresh_stats", season, run)


def refresh_schedule(sf: sessionmaker[Session], source: StatsSource, seasons: list[int]) -> int:
    def run(s: Session) -> int:
        wanted = {str(x) for x in seasons}
        games = [
            g
            for g in source.schedules()
            if g.get("season") in wanted and g.get("game_type") == "REG"
        ]
        s.execute(delete(NflGame).where(NflGame.season.in_(seasons)))
        s.add_all(
            NflGame(
                game_id=g["game_id"],
                season=int(g["season"]),
                week=int(g["week"]),
                home_team=g["home_team"],
                away_team=g["away_team"],
            )
            for g in games
        )
        return len(games)

    return _run_job(sf, "refresh_schedule", None, run)
