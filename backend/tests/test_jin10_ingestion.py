"""Jin10 flash ingestion: SSE/MCP wire parsing, item mapping, cursor paging.

The MCP server is faked with an httpx MockTransport so the whole
initialize → initialized → tools/call flow (and the SSE framing) is exercised
without touching the network. Persistence tests use the real test DB + Redis,
mirroring test_akshare_news.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from aether.ingestion import jin10
from aether.models.news import RawNews
from aether.storage import db as db_module
from aether.storage import redis_ as r

# ---------- fixtures -----------------------------------------------------


@pytest_asyncio.fixture
async def clean_news_and_redis() -> None:
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE raw_news RESTART IDENTITY CASCADE"))
    client = r.get_redis()
    async for key in client.scan_iter(match="dedup:news:*"):
        await client.delete(key)


# ---------- SSE / MCP transport fake ------------------------------------


def _sse(obj: dict) -> bytes:
    return f"event: message\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


def _make_transport(pages: list[dict], *, session_id: str = "SID-TEST") -> httpx.MockTransport:
    """Serve initialize/initialized plus `list_flash` pages in order.

    `pages` are the `data` sub-objects ({items, next_cursor, has_more}) returned
    by successive tool calls; once exhausted an empty final page is served.
    """
    state = {"page": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": session_id, "content-type": "text/event-stream"},
                content=_sse(
                    {"jsonrpc": "2.0", "id": body["id"], "result": {"serverInfo": {"name": "t"}}}
                ),
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/call":
            i = state["page"]
            state["page"] += 1
            data = (
                pages[i]
                if i < len(pages)
                else {"items": [], "has_more": False, "next_cursor": None}
            )
            payload = {"status": 200, "message": "success", "data": data}
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=_sse(
                    {
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": {
                            "content": [
                                {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
                            ],
                            "structuredContent": payload,
                        },
                    }
                ),
            )
        return httpx.Response(400, content=b"unexpected")

    return httpx.MockTransport(handler)


def _flash(url: str, content: str, ts: str = "2026-07-17T22:48:59+08:00") -> dict:
    return {"url": url, "content": content, "time": ts}


def _patch_settings(pages: list[dict], *, api_key: str = "sk-test", max_pages: int = 5):
    """Point jin10 at a mock transport and a stub Settings."""
    stub = SimpleNamespace(
        jin10_api_key=api_key,
        jin10_mcp_url="https://mock.jin10/mcp",
        jin10_max_pages_per_tick=max_pages,
    )
    transport = _make_transport(pages)
    return (
        patch.object(jin10, "get_settings", return_value=stub),
        patch.object(jin10, "_new_http_client", lambda: httpx.AsyncClient(transport=transport)),
    )


# ---------- pure parsing -------------------------------------------------


def test_parse_sse_json_single_line():
    body = 'event: message\ndata: {"a": 1}\n\n'
    assert jin10._parse_sse_json(body) == {"a": 1}


def test_parse_sse_json_joins_multiline_data():
    body = 'event: message\ndata: {"a":\ndata: 1}\n\n'
    assert jin10._parse_sse_json(body) == {"a": 1}


def test_parse_sse_json_raises_without_data_frame():
    with pytest.raises(jin10.Jin10Error):
        jin10._parse_sse_json("event: ping\n\n")


def test_title_prefers_bracketed_headline():
    content = "【伊朗：海峡仍被把控】金十数据7月17日讯，据报道…"
    assert jin10._title_from_content(content) == "伊朗：海峡仍被把控"


def test_title_falls_back_to_truncated_body():
    content = "x" * 200
    title = jin10._title_from_content(content)
    assert title.endswith("…") and len(title) <= 61


def test_parse_time_offset_to_utc():
    out = jin10._parse_time("2026-07-17T22:48:59+08:00")
    assert (out.hour, out.minute, out.tzinfo.utcoffset(None).total_seconds()) == (14, 48, 0)


def test_parse_time_garbage_falls_back_to_now():
    from datetime import UTC, datetime

    before = datetime.now(UTC)
    out = jin10._parse_time("not-a-time")
    assert before <= out <= datetime.now(UTC)


def test_items_from_payload_maps_and_skips_incomplete():
    payload = {
        "data": {
            "items": [
                _flash("https://flash.jin10.com/detail/1", "【标题A】正文A"),
                {"url": "", "content": "no url"},  # skipped
                {"url": "https://x/2", "content": ""},  # skipped
            ],
            "next_cursor": "1784297285927",
            "has_more": True,
        }
    }
    items, cursor, has_more = jin10._items_from_payload(payload)
    assert len(items) == 1
    assert items[0].source == "金十快讯"
    assert items[0].title == "标题A"
    assert items[0].url.endswith("/1")
    assert items[0].lang == "zh"
    assert (cursor, has_more) == ("1784297285927", True)


def test_items_from_payload_empty():
    items, cursor, has_more = jin10._items_from_payload({"data": {"items": []}})
    assert items == [] and cursor is None and has_more is False


# ---------- MCP client over mock transport ------------------------------


async def test_client_handshake_and_tool_call():
    transport = _make_transport([{"items": [_flash("https://x/1", "【h】b")], "has_more": False}])
    async with httpx.AsyncClient(transport=transport) as http:
        client = jin10.Jin10Client(http, "https://mock/mcp", "sk-test")
        await client.open()
        payload = await client.call_tool("list_flash", {})
    assert payload["data"]["items"][0]["url"] == "https://x/1"


async def test_client_tool_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "S"},
                content=_sse({"jsonrpc": "2.0", "id": body["id"], "result": {}}),
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            content=_sse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "bad arguments"}],
                    },
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = jin10.Jin10Client(http, "https://mock/mcp", "sk-test")
        await client.open()
        with pytest.raises(jin10.Jin10Error, match="bad arguments"):
            await client.call_tool("list_flash", {})


# ---------- tick end-to-end (real DB + Redis) ---------------------------


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_tick_writes_then_dedups():
    pages = [
        {
            "items": [
                _flash("https://flash.jin10.com/detail/a", "【A】aa"),
                _flash("https://flash.jin10.com/detail/b", "【B】bb"),
            ],
            "next_cursor": None,
            "has_more": False,
        }
    ]
    p_settings, p_http = _patch_settings(pages)
    with p_settings, p_http:
        n1 = await jin10.tick()
    # Same page again -> everything already seen.
    p_settings, p_http = _patch_settings(pages)
    with p_settings, p_http:
        n2 = await jin10.tick()

    assert n1["金十快讯"] == 2
    assert n2["金十快讯"] == 0
    async with db_module.session_scope() as session:
        count = await session.scalar(select(func.count()).select_from(RawNews))
    assert count == 2


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_tick_stops_paging_when_page_partially_seen():
    # Page 1 is entirely new (full page → keep going); page 2 overlaps → stop.
    full = [_flash(f"https://x/p1-{i}", f"【n{i}】c") for i in range(2)]
    pages = [
        {"items": full, "next_cursor": "c1", "has_more": True},
        {
            "items": [_flash("https://x/p1-0", "seen"), _flash("https://x/p2-new", "【new】c")],
            "next_cursor": "c2",
            "has_more": True,
        },
        {"items": [_flash("https://x/should-not-fetch", "【z】c")], "has_more": True},
    ]
    p_settings, p_http = _patch_settings(pages, max_pages=5)
    with p_settings, p_http:
        n = await jin10.tick()
    # 2 from page 1 + 1 new from page 2; page 3 never fetched.
    assert n["金十快讯"] == 3
    async with db_module.session_scope() as session:
        rows = (await session.execute(select(RawNews.url))).scalars().all()
    assert "https://x/should-not-fetch" not in rows


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_tick_respects_page_cap():
    # Every page is full & has_more → capped at max_pages tool calls.
    def page(i: int) -> dict:
        return {
            "items": [_flash(f"https://x/{i}-{j}", f"【c】{i}{j}") for j in range(2)],
            "next_cursor": f"cur{i}",
            "has_more": True,
        }

    pages = [page(i) for i in range(10)]
    p_settings, p_http = _patch_settings(pages, max_pages=3)
    with p_settings, p_http:
        n = await jin10.tick()
    assert n["金十快讯"] == 6  # 3 pages × 2 items, then the cap stops it


async def test_tick_no_op_without_api_key():
    stub = SimpleNamespace(jin10_api_key="", jin10_mcp_url="https://x", jin10_max_pages_per_tick=5)
    with patch.object(jin10, "get_settings", return_value=stub):
        n = await jin10.tick()
    assert n == {"金十快讯": 0}


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_tick_swallows_transport_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    stub = SimpleNamespace(
        jin10_api_key="sk", jin10_mcp_url="https://x/mcp", jin10_max_pages_per_tick=5
    )
    with (
        patch.object(jin10, "get_settings", return_value=stub),
        patch.object(
            jin10,
            "_new_http_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ),
    ):
        n = await jin10.tick()
    assert n == {"金十快讯": 0}
