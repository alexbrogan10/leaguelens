from datetime import timedelta

import httpx
import pytest

from leaguelens.cache import DbCache, MemoryCache
from leaguelens.clients.ratelimit import TokenBucket
from leaguelens.clients.sleeper import (
    FixtureSleeperClient,
    HttpSleeperClient,
    RoutingSleeperClient,
    SleeperError,
)


def mock_client(handler, cache=None):
    calls = []

    def wrapped(request: httpx.Request):
        calls.append(request.url.path)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(wrapped))
    client = HttpSleeperClient(
        cache or MemoryCache(), base_url="https://x/v1", max_rps=1000, http=http
    )
    return client, calls


def test_http_client_caches_responses():
    client, calls = mock_client(lambda r: httpx.Response(200, json={"league_id": "1"}))
    assert client.get_league("1") == {"league_id": "1"}
    assert client.get_league("1") == {"league_id": "1"}
    assert calls == ["/v1/league/1"]


def test_http_client_404_and_null_are_none():
    client, _ = mock_client(lambda r: httpx.Response(404))
    assert client.get_league("x") is None
    client, _ = mock_client(lambda r: httpx.Response(200, text="null"))
    assert client.get_user("ghost") is None


def test_http_client_errors():
    client, _ = mock_client(lambda r: httpx.Response(429))
    with pytest.raises(SleeperError) as e:
        client.get_league("1")
    assert e.value.status == 429

    def boom(request):
        raise httpx.ConnectError("down")

    client, _ = mock_client(boom)
    with pytest.raises(SleeperError):
        client.get_state()


def test_lists_ignore_garbage():
    client, _ = mock_client(lambda r: httpx.Response(200, json=[{"roster_id": 1}, None, 3]))
    assert client.get_rosters("1") == [{"roster_id": 1}]


def test_db_cache_persists_and_expires(container):
    cache = DbCache(container.session_factory)
    cache.set("k", "v", timedelta(minutes=5), source="t")
    cache.set("forever", "x", None)
    cache.set("old", "y", timedelta(seconds=-1))
    fresh = DbCache(container.session_factory)  # new memory layer, reads from DB
    assert fresh.get("k") == "v"
    assert fresh.get("forever") == "x"
    assert fresh.get("old") is None
    assert fresh.get("missing") is None


def test_token_bucket_waits_when_empty():
    now = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    bucket = TokenBucket(2, burst=2, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        bucket.acquire()
    assert slept == [pytest.approx(0.5)]
    with pytest.raises(ValueError):
        TokenBucket(0)


def test_routing_sends_demo_ids_to_fixtures(tmp_path):
    (tmp_path / "league").mkdir()
    (tmp_path / "league" / "demo_1.json").write_text('{"league_id": "demo_1"}')
    live, calls = mock_client(lambda r: httpx.Response(200, json={"league_id": "live"}))
    router = RoutingSleeperClient(live=live, demo=FixtureSleeperClient(tmp_path))
    assert router.get_league("demo_1") == {"league_id": "demo_1"}
    assert router.get_league("123") == {"league_id": "live"}
    assert calls == ["/v1/league/123"]
