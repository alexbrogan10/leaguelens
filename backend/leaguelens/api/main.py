"""FastAPI application."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from leaguelens import __version__
from leaguelens.clients.sleeper import SleeperError
from leaguelens.config import get_settings
from leaguelens.container import Container, build_container
from leaguelens.models import JobRun
from leaguelens.schemas import DashboardOut, LeagueOut, StateOut, UserLeaguesOut
from leaguelens.services.league import LeagueService, NotFoundError


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_league_service(c: ContainerDep) -> LeagueService:
    return LeagueService(c.sleeper)


LeagueDep = Annotated[LeagueService, Depends(get_league_service)]


def create_app(container: Container | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LeagueLens API", version=__version__)
    app.state.container = container or build_container(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SleeperError)
    def _sleeper(_: Request, exc: SleeperError) -> JSONResponse:
        status = 503 if exc.status in (None, 429) or exc.status >= 500 else 502
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    @app.get("/api/health")
    def health(c: ContainerDep) -> dict[str, object]:
        db_ok = True
        last_refresh = None
        try:
            with c.session_factory() as s:
                s.execute(text("SELECT 1"))
                run = s.scalars(
                    select(JobRun)
                    .where(JobRun.status == "ok")
                    .order_by(JobRun.finished_at.desc())
                    .limit(1)
                ).first()
                last_refresh = run.finished_at.isoformat() if run and run.finished_at else None
        except Exception:
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "db": db_ok, "last_refresh": last_refresh}

    @app.get("/api/state", response_model=StateOut)
    def state(c: ContainerDep) -> StateOut:
        s = c.sleeper.get_state()
        return StateOut(
            season=str(s.get("league_season") or s.get("season")),
            week=int(s.get("week") or 0),
            season_type=str(s.get("season_type") or "regular"),
        )

    @app.get("/api/users/{username}/leagues", response_model=UserLeaguesOut)
    def user_leagues(
        username: str, svc: LeagueDep, season: Annotated[str | None, Query()] = None
    ) -> UserLeaguesOut:
        if season is not None and not season.isdigit():
            raise HTTPException(422, "season must be a year")
        return svc.user_leagues(username, season)

    @app.get("/api/leagues/{league_id}", response_model=LeagueOut)
    def league(league_id: str, svc: LeagueDep) -> LeagueOut:
        return svc.league_out(svc.context(league_id))

    @app.get("/api/leagues/{league_id}/dashboard", response_model=DashboardOut)
    def dashboard(league_id: str, svc: LeagueDep) -> DashboardOut:
        return svc.dashboard(league_id)

    return app
