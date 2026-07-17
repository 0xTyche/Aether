"""金十快讯 (Jin10 Flash) ingestion via Jin10's MCP server.

Jin10 exposes its data only through an MCP endpoint (no plain REST), so unlike
the other fetchers this one speaks a thin slice of the MCP wire protocol over
HTTP:

    initialize → notifications/initialized → tools/call("list_flash")

We deliberately do NOT pull in the `mcp` client SDK: the server is a remote
streamable-HTTP endpoint (no subprocess), and we only ever call one read-only
tool on a timer, so a small httpx adapter is lighter and fully under our
control. Everything MCP-specific lives in `Jin10Client`; `tick()` then looks
like every other ingester and funnels into `common.persist_fresh`.

Flash items ship only {content, time, url} — no id, no title — so we derive a
title from the leading 【…】 headline (falling back to a truncated body) and
use the stable detail URL as the dedup key.
"""

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from aether.config import get_settings
from aether.ingestion.common import ParsedItem, persist_fresh, short_title

logger = structlog.get_logger(__name__)

SOURCE_NAME = "金十快讯"

_PROTOCOL_VERSION = "2025-06-18"
_HTTP_TIMEOUT = httpx.Timeout(15.0)
# Jin10 embeds the headline as 【标题】 at the very start of a flash body.
_HEADLINE_RE = re.compile(r"^\s*【(.+?)】")


class Jin10Error(RuntimeError):
    """Protocol- or tool-level failure talking to the Jin10 MCP server."""


class Jin10Client:
    """Minimal MCP-over-HTTP client for Jin10's streamable-HTTP endpoint.

    One instance is one MCP session: build it, `await open()` to run the
    handshake, then `call_tool(...)`. Cheap enough to construct fresh per tick,
    which sidesteps having to detect and recover from session expiry.
    """

    def __init__(self, http: httpx.AsyncClient, url: str, api_key: str) -> None:
        self._http = http
        self._url = url
        self._api_key = api_key
        self._session_id: str | None = None
        self._next_id = 0

    def _headers(self) -> dict[str, str]:
        # The server rejects any request whose Accept lacks either type (HTTP 400).
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": _PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        return headers

    def _rpc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        resp = await self._http.post(
            self._url, headers=self._headers(), content=json.dumps(payload)
        )
        resp.raise_for_status()
        return resp

    async def open(self) -> None:
        """Run initialize + the initialized ack so tool calls are accepted."""
        resp = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._rpc_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "aether", "version": "0.1"},
                },
            }
        )
        self._session_id = resp.headers.get("mcp-session-id")
        if not self._session_id:
            raise Jin10Error("initialize returned no mcp-session-id")
        # Surface an init-time JSON-RPC error early rather than on first call.
        _parse_sse_json(resp.text)
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool and return its result payload (structured JSON)."""
        resp = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._rpc_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        message = _parse_sse_json(resp.text)
        result = message.get("result")
        if result is None:
            raise Jin10Error(f"{name}: {message.get('error')}")
        if result.get("isError"):
            raise Jin10Error(f"{name} returned isError: {_first_text(result)}")
        return _result_payload(result)


# ---------- SSE / result parsing ----------------------------------------


def _parse_sse_json(body: str) -> dict[str, Any]:
    """Extract the JSON-RPC message from an SSE response body.

    An event's data may span multiple `data:` lines joined with newlines (SSE
    spec); this server sends it on one line today, but we join defensively.
    """
    data_lines = [
        line[len("data:") :].lstrip() for line in body.splitlines() if line.startswith("data:")
    ]
    if not data_lines:
        raise Jin10Error("no SSE data frame in response")
    return json.loads("\n".join(data_lines))


def _first_text(result: dict[str, Any]) -> str:
    for c in result.get("content", []):
        if c.get("type") == "text":
            return c.get("text", "")
    return ""


def _result_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Prefer `structuredContent`; fall back to the JSON in the text content."""
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    text = _first_text(result)
    return json.loads(text) if text else {}


# ---------- flash item mapping ------------------------------------------


def _title_from_content(content: str) -> str:
    """Use the bracketed 【headline】 as the title; else a truncated body."""
    m = _HEADLINE_RE.match(content or "")
    return m.group(1).strip() if m else short_title(content)


def _parse_time(raw: Any) -> datetime:
    """Jin10 ships ISO-8601 with a +08:00 offset; normalize to UTC."""
    try:
        return datetime.fromisoformat(str(raw)).astimezone(UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _items_from_payload(
    payload: dict[str, Any],
) -> tuple[list[ParsedItem], str | None, bool]:
    """Map a `list_flash` payload to items plus (next_cursor, has_more)."""
    data = payload.get("data") or {}
    items: list[ParsedItem] = []
    for it in data.get("items") or []:
        url = (it.get("url") or "").strip()
        content = (it.get("content") or "").strip()
        if not url or not content:
            continue
        items.append(
            ParsedItem(
                source=SOURCE_NAME,
                url=url,
                title=_title_from_content(content),
                body=content,
                published_at=_parse_time(it.get("time")),
                lang="zh",
            )
        )
    next_cursor = data.get("next_cursor")
    return items, (str(next_cursor) if next_cursor else None), bool(data.get("has_more"))


def _new_http_client() -> httpx.AsyncClient:
    """Seam so tests can inject a MockTransport-backed client."""
    return httpx.AsyncClient(timeout=_HTTP_TIMEOUT)


async def tick() -> dict[str, int]:
    """Scheduler entry point: pull the latest flash items.

    Follows the cursor into older pages only until a page contains something we
    already stored (we've caught up with the previous tick), bounded by a hard
    page cap so a burst can't turn one tick into an unbounded backfill.
    """
    settings = get_settings()
    if not settings.jin10_api_key:
        logger.warning("jin10.skipped_no_api_key")
        return {SOURCE_NAME: 0}

    max_pages = settings.jin10_max_pages_per_tick
    written_total = 0
    try:
        async with _new_http_client() as http:
            client = Jin10Client(http, settings.jin10_mcp_url, settings.jin10_api_key)
            await client.open()
            cursor: str | None = None
            pages = 0
            while pages < max_pages:
                args = {"cursor": cursor} if cursor else {}
                payload = await client.call_tool("list_flash", args)
                items, next_cursor, has_more = _items_from_payload(payload)
                pages += 1
                if not items:
                    break
                written = await persist_fresh(items)
                written_total += written
                # A partial write means this page overlapped already-seen items,
                # i.e. we've caught up — no need to page further back.
                if written < len(items) or not has_more or not next_cursor:
                    break
                cursor = next_cursor
            else:
                logger.warning("jin10.page_cap_reached", max_pages=max_pages)
    except Exception as exc:
        logger.warning("jin10.tick_failed", error=str(exc))
        return {SOURCE_NAME: written_total}

    logger.info("jin10.ingested", written=written_total, pages=pages)
    return {SOURCE_NAME: written_total}
