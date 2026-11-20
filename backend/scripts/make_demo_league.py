"""Generate the bundled demo league (leaguelens/demo_data) from locally loaded stats.

The demo league has fictional managers but real NFL players and real nflverse stats:
rosters come from a mock snake draft, and each week's score is the actual fantasy output
of the lineup a sensible manager would have set. Three seasons are linked through
``previous_league_id`` so the history page has something to show.

Usage (after `python -m leaguelens.jobs all --season 2024 --season 2025 --season 2026`):

    python scripts/make_demo_league.py --through-week 10
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from leaguelens.config import get_settings
from leaguelens.db import make_engine, make_session_factory
from leaguelens.models import Player, PlayerWeekStat
from leaguelens.services.valuation import stat_line
from leaguelens.valuation.scoring import fantasy_points

OUT = Path(__file__).resolve().parents[1] / "leaguelens" / "demo_data"
SEASONS = [2024, 2025, 2026]
CURRENT = 2026
SCORING = {
    "pass_yd": 0.04,
    "pass_td": 4,
    "pass_int": -1,
    "pass_2pt": 2,
    "rush_yd": 0.1,
    "rush_td": 6,
    "rush_2pt": 2,
    "rec": 1,
    "rec_yd": 0.1,
    "rec_td": 6,
    "rec_2pt": 2,
    "fum_lost": -2,
}
ROSTER_POSITIONS = [
    "QB",
    "RB",
    "RB",
    "WR",
    "WR",
    "TE",
    "FLEX",
    "K",
    "DEF",
    "BN",
    "BN",
    "BN",
    "BN",
    "BN",
    "BN",
]
STARTERS = [p for p in ROSTER_POSITIONS if p != "BN"]
FLEX = {"FLEX": ("RB", "WR", "TE")}
MANAGERS = [
    ("Morgan", "Gridiron Gurus"),
    ("Riley", "Fourth & Long"),
    ("Casey", "Red Zone Rebels"),
    ("Jordan", "The Waiver Wire"),
    ("Taylor", "Blitz Brigade"),
    ("Avery", "Hail Mary Heroes"),
    ("Quinn", "Pigskin Prophets"),
    ("Jamie", "End Zone Elite"),
    ("Drew", "Sack Masters"),
    ("Skyler", "Two-Point Tries"),
    ("Parker", "Audible Ambush"),
    ("Reese", "Fumble Factory"),
]
TEAMS = len(MANAGERS)
REG_WEEKS = 14
PLAYOFF_START = 15


def write(path: str, data: object) -> None:
    file = OUT / f"{path}.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, separators=(",", ":")))


def league_id(season: int) -> str:
    return f"demo_{season}"


def round_robin(n: int, weeks: int) -> list[list[tuple[int, int]]]:
    ids = list(range(1, n + 1))
    out = []
    for _ in range(weeks):
        out.append([(ids[i], ids[n - 1 - i]) for i in range(n // 2)])
        ids = [ids[0], ids[-1], *ids[1:-1]]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--through-week", type=int, required=True, help="last completed 2026 week")
    args = ap.parse_args()
    rng = random.Random(2026)

    sf = make_session_factory(make_engine(get_settings().database_url))
    with sf() as s:
        players = {p.sleeper_id: p for p in s.scalars(select(Player))}
        stats = s.scalars(select(PlayerWeekStat).where(PlayerWeekStat.season.in_(SEASONS)))
        points: dict[tuple[int, str], dict[int, float]] = defaultdict(dict)
        for row in stats:
            points[(row.season, row.gsis_id)][row.week] = fantasy_points(
                stat_line(row), SCORING, row.position or ""
            )

    if OUT.exists():
        shutil.rmtree(OUT)
    write(
        "user/demo",
        {
            "user_id": "demo_user",
            "username": "demo",
            "display_name": "Demo Manager",
            "avatar": None,
        },
    )
    users = [
        {
            "user_id": "demo_user" if i == 0 else f"demo_u{i + 1}",
            "display_name": name,
            "avatar": None,
            "metadata": {"team_name": team},
        }
        for i, (name, team) in enumerate(MANAGERS)
    ]
    kickers = [p for p in players.values() if p.position == "K" and p.team]
    defenses = [p for p in players.values() if p.position == "DEF" and p.team]

    for season in SEASONS:
        current = season == CURRENT
        last_week = args.through_week if current else 17
        # Draft board: previous season's PPG for the live season, same season otherwise.
        rank_season = season - 1 if current else season
        board = []
        for p in players.values():
            if p.position not in ("QB", "RB", "WR", "TE") or not p.gsis_id or not p.team:
                continue
            wk = points.get((rank_season, p.gsis_id)) or points.get((season, p.gsis_id))
            if not wk or len(wk) < 4:
                continue
            value = sum(wk.values()) / len(wk)
            value *= {"QB": 0.62, "RB": 1.12, "WR": 1.0, "TE": 0.85}[p.position]
            board.append((value + rng.uniform(-2.5, 2.5), p))
        board.sort(key=lambda x: -x[0])

        rosters: dict[int, list[Player]] = {i: [] for i in range(1, TEAMS + 1)}
        caps = {"QB": 2, "RB": 5, "WR": 5, "TE": 2}
        for rnd in range(13):
            order = range(1, TEAMS + 1) if rnd % 2 == 0 else range(TEAMS, 0, -1)
            for rid in order:
                have = defaultdict(int)
                for p in rosters[rid]:
                    have[p.position] += 1
                pick = next((b for b in board if have[b[1].position] < caps[b[1].position]), None)
                if pick:
                    board.remove(pick)
                    rosters[rid].append(pick[1])
        rng.shuffle(kickers)
        rng.shuffle(defenses)
        for rid in rosters:
            rosters[rid] += [kickers[rid], defenses[rid]]

        def week_points(p: Player, week: int) -> float:
            if p.position in ("K", "DEF"):
                return round(rng.uniform(2, 16), 2)
            return points.get((season, p.gsis_id or ""), {}).get(week, 0.0)

        def lineup(rid: int, week: int) -> list[Player]:
            def form(p: Player) -> float:
                wk = points.get((season, p.gsis_id or ""), {})
                prior = [v for w, v in wk.items() if w < week][-4:]
                return sum(prior) / len(prior) if prior else 5.0

            pool = sorted(rosters[rid], key=form, reverse=True)
            chosen: list[Player] = []
            for slot in sorted(STARTERS, key=lambda s: s in FLEX):
                elig = FLEX.get(slot, (slot,))
                pick = next((p for p in pool if p.position in elig and p not in chosen), None)
                if pick:
                    chosen.append(pick)
            return chosen

        lid = league_id(season)
        schedule = round_robin(TEAMS, REG_WEEKS)
        week_scores: dict[int, dict[int, float]] = {}
        for week in range(1, min(last_week, 17) + 1):
            entries = []
            scores = {}
            for rid in rosters:
                starters = lineup(rid, week)
                pts = {p.sleeper_id: week_points(p, week) for p in rosters[rid]}
                total = round(sum(pts[p.sleeper_id] for p in starters), 2)
                scores[rid] = total
                entries.append(
                    {
                        "roster_id": rid,
                        "points": total,
                        "starters": [p.sleeper_id for p in starters],
                        "players": [p.sleeper_id for p in rosters[rid]],
                        "players_points": pts,
                        "matchup_id": None,
                    }
                )
            if week <= REG_WEEKS:
                for mid, (a, b) in enumerate(schedule[week - 1], start=1):
                    for e in entries:
                        if e["roster_id"] in (a, b):
                            e["matchup_id"] = mid
            week_scores[week] = scores
            write(f"league/{lid}/matchups/{week}", entries)

        # Final records (regular season) for rosters.settings and playoff seeding.
        rec = {
            rid: {"wins": 0, "losses": 0, "ties": 0, "fpts": 0.0, "fpts_against": 0.0}
            for rid in rosters
        }
        for week in range(1, min(last_week, REG_WEEKS) + 1):
            for a, b in schedule[week - 1]:
                sa, sb = week_scores[week][a], week_scores[week][b]
                rec[a]["fpts"] += sa
                rec[b]["fpts"] += sb
                rec[a]["fpts_against"] += sb
                rec[b]["fpts_against"] += sa
                if sa > sb:
                    rec[a]["wins"] += 1
                    rec[b]["losses"] += 1
                elif sb > sa:
                    rec[b]["wins"] += 1
                    rec[a]["losses"] += 1
                else:
                    rec[a]["ties"] += 1
                    rec[b]["ties"] += 1

        bracket = []
        if not current:
            seeds = sorted(rosters, key=lambda r: (-rec[r]["wins"], -rec[r]["fpts"]))

            def play(m: int, rnd: int, t1: int, t2: int, week: int, p: int | None = None):
                s1, s2 = week_scores[week][t1], week_scores[week][t2]
                w, lo = (t1, t2) if s1 >= s2 else (t2, t1)
                entry = {"r": rnd, "m": m, "t1": t1, "t2": t2, "w": w, "l": lo}
                if p:
                    entry["p"] = p
                bracket.append(entry)
                return w, lo

            w1, _ = play(1, 1, seeds[2], seeds[5], 15)
            w2, _ = play(2, 1, seeds[3], seeds[4], 15)
            s1, l1 = play(3, 2, seeds[0], w2, 16)
            s2, l2 = play(4, 2, seeds[1], w1, 16)
            play(5, 3, s1, s2, 17, p=1)
            play(6, 3, l1, l2, 17, p=3)
            write(f"league/{lid}/winners_bracket", bracket)

        write(
            f"league/{lid}",
            {
                "league_id": lid,
                "name": "LeagueLens Demo League",
                "season": str(season),
                "status": "in_season" if current else "complete",
                "sport": "nfl",
                "total_rosters": TEAMS,
                "roster_positions": ROSTER_POSITIONS,
                "scoring_settings": SCORING,
                "avatar": None,
                "previous_league_id": league_id(season - 1) if season > SEASONS[0] else None,
                "settings": {
                    "playoff_week_start": PLAYOFF_START,
                    "playoff_teams": 6,
                    "start_week": 1,
                    "league_average_match": 0,
                    "num_teams": TEAMS,
                },
            },
        )
        write(f"league/{lid}/users", users)
        write(
            f"league/{lid}/rosters",
            [
                {
                    "roster_id": rid,
                    "owner_id": users[rid - 1]["user_id"],
                    "players": [p.sleeper_id for p in ps],
                    "starters": [p.sleeper_id for p in lineup(rid, min(last_week + 1, 17))],
                    "settings": {
                        k: (round(v) if isinstance(v, float) else v) for k, v in rec[rid].items()
                    },
                }
                for rid, ps in rosters.items()
            ],
        )
        write(
            f"user/demo_user/leagues/nfl/{season}",
            [
                {
                    "league_id": lid,
                    "name": "LeagueLens Demo League",
                    "season": str(season),
                    "status": "in_season" if current else "complete",
                    "total_rosters": TEAMS,
                    "avatar": None,
                }
            ],
        )
    print(f"Wrote demo league to {OUT}")


if __name__ == "__main__":
    main()
