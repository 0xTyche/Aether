"""AKShare news ingestion: shape mappers, dedup, source isolation."""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from aether.ingestion import akshare_news as ak_news
from aether.models.news import RawNews
from aether.storage import db as db_module
from aether.storage import redis_ as r


@pytest_asyncio.fixture
async def clean_news_and_redis() -> None:
    async with db_module.session_scope() as session:
        await session.execute(text("TRUNCATE TABLE raw_news RESTART IDENTITY CASCADE"))
    client = r.get_redis()
    async for key in client.scan_iter(match="dedup:news:*"):
        await client.delete(key)


# ---------- pure parsing -------------------------------------------------

def test_parse_cst_to_utc_offset():
    out = ak_news._parse_cst("2026-06-12 17:31:14")
    assert out == datetime(2026, 6, 12, 9, 31, 14, tzinfo=UTC)


def test_parse_cst_falls_back_to_now_on_garbage():
    before = datetime.now(UTC)
    out = ak_news._parse_cst("not-a-date")
    after = datetime.now(UTC)
    assert before <= out <= after


def test_synth_url_is_stable_and_distinct_per_input():
    a = ak_news._synth_url("东财快讯", "title-a", datetime(2026, 1, 1, tzinfo=UTC))
    a_again = ak_news._synth_url("东财快讯", "title-a", datetime(2026, 1, 1, tzinfo=UTC))
    b = ak_news._synth_url("东财快讯", "title-b", datetime(2026, 1, 1, tzinfo=UTC))
    assert a == a_again
    assert a != b
    assert a.startswith("akshare://东财快讯/")


def test_short_title_truncates_with_ellipsis():
    assert ak_news.short_title("x" * 30, max_len=20) == "x" * 20 + "…"
    assert ak_news.short_title("short") == "short"


# ---------- per-source mappers ------------------------------------------

def test_fetch_cjzc_maps_dataframe_to_parsed_items():
    df = pd.DataFrame([
        {"标题": "财经早餐 6月12日", "摘要": "今日要闻摘要",
         "发布时间": "2026-06-12 06:00:00", "链接": "https://example.com/a"},
    ])
    with patch.object(ak_news.ak, "stock_info_cjzc_em", return_value=df):
        items = ak_news._fetch_cjzc()
    assert len(items) == 1
    it = items[0]
    assert it.source == "财经早餐"
    assert it.title == "财经早餐 6月12日"
    assert it.url == "https://example.com/a"
    assert it.lang == "zh"


def test_fetch_global_sina_uses_truncated_body_as_title():
    df = pd.DataFrame([
        {"时间": "2026-06-12 17:33:00", "内容": "短内容"},
        {"时间": "2026-06-12 17:34:00", "内容": "x" * 200},
    ])
    with patch.object(ak_news.ak, "stock_info_global_sina", return_value=df):
        items = ak_news._fetch_global_sina()
    assert len(items) == 2
    assert items[0].title == "短内容"
    assert items[1].title.endswith("…")
    # No upstream URL → synthesized.
    assert all(it.url.startswith("akshare://新浪快讯/") for it in items)


def test_fetch_global_futu_falls_back_to_body_when_title_empty():
    df = pd.DataFrame([
        {"标题": "", "内容": "南向资金净卖出 39.42 亿元",
         "发布时间": "2026-06-12 09:31:12", "链接": "https://futu.example/a"},
    ])
    with patch.object(ak_news.ak, "stock_info_global_futu", return_value=df):
        items = ak_news._fetch_global_futu()
    assert len(items) == 1
    assert items[0].title.startswith("南向资金")
    assert items[0].url == "https://futu.example/a"


def test_fetch_global_ths_drops_rows_with_no_title_or_body():
    df = pd.DataFrame([
        {"标题": "", "内容": "", "发布时间": "2026-06-12 09:33:00", "链接": ""},
        {"标题": "valid", "内容": "body", "发布时间": "2026-06-12 09:34:00", "链接": ""},
    ])
    with patch.object(ak_news.ak, "stock_info_global_ths", return_value=df):
        items = ak_news._fetch_global_ths()
    assert [i.title for i in items] == ["valid"]


# ---------- end-to-end ingest -------------------------------------------

@pytest.mark.usefixtures("clean_news_and_redis")
async def test_ingest_source_writes_then_dedups():
    df = pd.DataFrame([
        {"标题": "A", "摘要": "a", "发布时间": "2026-06-12 17:00:00",
         "链接": "https://example.com/a"},
        {"标题": "B", "摘要": "b", "发布时间": "2026-06-12 17:01:00",
         "链接": "https://example.com/b"},
    ])
    with patch.object(ak_news.ak, "stock_info_global_em", return_value=df):
        n1 = await ak_news.ingest_source("东财快讯", ak_news._fetch_global_em)
        n2 = await ak_news.ingest_source("东财快讯", ak_news._fetch_global_em)
    assert n1 == 2
    assert n2 == 0
    async with db_module.session_scope() as session:
        count = await session.scalar(select(func.count()).select_from(RawNews))
    assert count == 2


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_ingest_all_sources_isolates_per_source_failure():
    df_ok = pd.DataFrame([
        {"标题": "X", "摘要": "x", "发布时间": "2026-06-12 17:00:00",
         "链接": "https://example.com/x"},
    ])
    def boom() -> list[ak_news.ParsedItem]:
        raise RuntimeError("simulated upstream blip")

    sources = {
        "ok": lambda: ak_news._fetch_global_em(),
        "bad": boom,
    }
    with patch.object(ak_news.ak, "stock_info_global_em", return_value=df_ok):
        result = await ak_news.ingest_all_sources(sources)
    assert result["ok"] == 1
    assert result["bad"] == 0


@pytest.mark.usefixtures("clean_news_and_redis")
async def test_fetch_failure_returns_zero_without_raising():
    def boom() -> list[ak_news.ParsedItem]:
        raise RuntimeError("upstream gone")
    n = await ak_news.ingest_source("test", boom)
    assert n == 0
