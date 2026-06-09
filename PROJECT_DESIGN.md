# Aether · 以太 — 项目设计文档

> **一句话**：全球金融市场是一片"以太"，宏观事件如波在其中传导。Aether 让看不见的传导变得肉眼可见。
> 像 Flightradar24 显示飞机航线一样，显示"事件冲击波"从震源（某国/央行）穿透以太抵达全球资产的路径与方向。

---

## 0. 命名、许可证 & 来源声明

### 0.1 项目命名

**Aether**（以太）—— 取自古典物理学概念："充满宇宙、传递光与电磁波的不可见媒介"。本项目把全球金融市场视为"金融以太"：宏观事件（央行决议、地缘冲突、经济数据）像电磁波一样在其中传导，引发跨资产、跨地域的连锁反应。Aether 的使命是把这种传导**可视化**。

### 0.2 License

**License**：本项目采用 **AGPL-3.0-only**。

**为什么是 AGPL**：Aether 从 [koala73/worldmonitor](https://github.com/koala73/worldmonitor)（AGPL-3.0-only）的"金融变体" `finance.worldmonitor.app` 抽取核心地图模块（GeoJSON 数据 + 几何命中检测）作为基础，按 AGPL 传染性条款，整个 Aether 项目须以 AGPL-3.0 发布。

**法律后果**：
- 任何分发（含通过网络对外服务）须向使用者提供完整源代码
- 修改后的代码也必须以 AGPL-3.0 发布
- 不可闭源商业化、不可作为闭源 SaaS 出售
- 详见 §13 地图模块策略中的合规说明

**致谢**：
- [worldmonitor](https://worldmonitor.app) by [@koala73](https://github.com/koala73) — 地图分块与国家几何命中算法的来源
- [PolyWorld](https://github.com/AmazingAng/PolyWorld) by [@AmazingAng](https://github.com/AmazingAng) — UI 布局与脉冲动画模式参考
- [Natural Earth](https://www.naturalearthdata.com/) — 国家边界基础数据（Public Domain）

---

## 1. 产品定位

### 1.1 价值主张

当某地发生宏观事件（央行决议、地缘冲突、经济数据公布）时，**1 秒内**告诉用户：

1. **谁被影响** —— 哪些国家 / 资产受波及
2. **影响多大** —— 实际价格变动幅度
3. **方向如何** —— 规则/LLM 给出的"预期方向" vs "实际方向"对照

### 1.2 典型场景

> **场景 A：日央行加息**
> - 地图日本亮起红色脉冲
> - 虚线弧射向：美国（美元/日元、美债）、欧洲（EUR/JPY）、澳洲（AUD/JPY 套息交易）
> - 右栏资产卡片：
>   - USD/JPY  预期 ↓  实际 ↓1.2%  ✅
>   - 日经 225  预期 ↓  实际 ↓2.0%  ✅
>   - 美债 10Y  预期 ↑  实际 ↑5bp  ✅
>   - 黄金     预期 ↑  实际 ↑0.3%  ✅

> **场景 B：中东冲突升级**
> - 地图中东亮起
> - 虚线射向：能源市场、欧洲（天然气）、避险资产
> - 资产卡片：布伦特原油 ↑、黄金 ↑、瑞郎 ↑、欧元区股指 ↓

### 1.3 非目标（明确不做）

- ❌ 提供交易/下单功能
- ❌ 投资建议或仓位推荐
- ❌ 覆盖所有新闻（只关心**可能传导到市场**的事件）
- ❌ 多语言多站点变体（worldmonitor 那种）
- ❌ 移动端原生 app（先做 PWA 就够）

---

## 2. UI 设计

### 2.1 主界面（三栏布局）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  World Info       [搜索]                  🟢 LIVE   ⚙️ 设置   📊 历史回看    │
├──────────────┬───────────────────────────────────────────┬─────────────────-─┤
│              │                                           │                   │
│ 📰 NEWS      │              🌍 WORLD MAP                 │  💹 IMPACT        │
│              │                                           │                   │
│ 14:32 🔴     │       ╭─────╮                             │  从事件：         │
│ BoJ 加息     │      /  EU  \    ╲                        │  BoJ 加息 25bp    │
│ 25bp 至0.5%  │      \      /    ╲ ─ ─ ─ ╮              │  ─────────────    │
│              │       ╰─────╯           ╲ │              │                   │
│ 14:28        │            ╲              ╲│              │  USD/JPY          │
│ Fed 官员讲话 │             ╲              ●JP ⚡         │  预期 ↓ 实际 -1.2%│
│              │              ╲            ╱  │             │  ▼▼ -1.2% ✅     │
│ 14:15 🟡     │               ╲          ╱   │             │  ━━━━━━━━━━━━━━  │
│ 美 CPI 公布  │              ╲ ╲        ╱    │             │                   │
│ +3.2% YoY    │           ●US ●         ╱    │            │  Nikkei 225       │
│              │            │  ╲        ╱    │             │  预期 ↓ 实际 -2.0%│
│ 14:02        │            │   ╲      ╱     │             │  ▼▼ -2.0% ✅     │
│ ECB 副行长…  │            │    ╲ ─ ─        │             │  ━━━━━━━━━━━━━━  │
│              │           AU●               │             │                   │
│ [更多…]      │                              │             │  US 10Y Yield     │
│              │                              │             │  预期 ↑ 实际 +5bp │
│              │  ●= 事件震源  →= 影响传导    │             │  ▲▲ +5bp ✅      │
│              │  ⚡= 当前选中事件              │             │                   │
│              │                              │             │  ...（更多资产）  │
└──────────────┴───────────────────────────────────────────┴─────────────────-─┘
```

### 2.2 关键交互

| 动作 | 效果 |
|---|---|
| 点击左栏新闻 | 地图 zoom 到震源、弧线动画播放、右栏切换为该事件影响 |
| 点击地图国家 pin | 显示该国今日所有事件列表 |
| 点击右栏资产卡片 | 弹出 sparkline 微图，显示过去 24h 价格走势 |
| 顶部"历史回看" | 时间轴模式：拖动时间，重放历史事件的传导动画 |
| 鼠标 hover 弧线 | tooltip 显示规则 ID / LLM 解释（"为什么是这条传导路径"） |

### 2.3 视觉语言

- **事件严重度**：🟢 低 / 🟡 中 / 🔴 高 → 配色 #4ade80 / #facc15 / #ef4444
- **传导弧线**：白色半透明虚线，从震源向外，速度感（动画 0.8s）
- **资产涨跌**：绿涨红跌（中国习惯）/ 可设置反转（西方习惯）
- **底图**：深色（#0a0f1a），低饱和度，突出数据
- **字体**：Inter（英数）+ Noto Sans SC（中文）

---

## 3. 功能优先级

### P0（MVP 必须）
| # | 功能 | 验收标准 |
|---|---|---|
| 1 | 央行 RSS 抓取（5 个：Fed/ECB/BoJ/BoE/PBoC） | 5 分钟内能看到新发公告 |
| 2 | Reuters / FT 抓取 | 同上 |
| 3 | 规则引擎（≥20 条手写规则） | 命中常见央行/CPI/NFP 事件 |
| 4 | LLM 兜底分析（Claude API） | 未命中规则时，30s 内出结果 |
| 5 | Binance WS 行情订阅（加密 + 代币化美股） | 实时价格变动推送前端 |
| 6 | AKShare 拉取 A股/港股/外汇 | 1 分钟间隔轮询 |
| 7 | 三栏 Dashboard UI | 新闻流、世界地图、资产卡片 |
| 8 | WebSocket 推送（事件、影响、价格） | 浏览器实时刷新 |
| 9 | 弧线动画（ArcLayer） | 事件触发后弧线播放 |
| 10 | "预期 vs 实际"对照 | 资产卡片显示两个箭头 |
| 11 | **国家分块点击**（基于 worldmonitor 抽取的 ADM0 几何） | 点击地图任意区域返回 ISO2 国家码 |
| 12 | **部署区域边界覆盖层** | 加载 `boundary-overrides.geojson` 覆盖上游几何，适配目标部署区域 |
| 13 | **经济 region 双轨高亮**（6 个：欧元区/G7/G20/OPEC+/BRICS/ASEAN） | 事件命中时批量高亮成员国 + 联动该 region 的资产卡片 |

### P1（MVP 之后 1–2 周）
- 历史事件回看（时间轴拖动）
- 资产 sparkline 微图
- 事件搜索 / 过滤（按国家、按资产、按严重度）
- 规则可视化编辑器（不用改代码加新规则）
- GDELT 接入（地缘事件）
- FRED 经济数据接入

### P2（长期）
- 用户自定义资产 watchlist
- 邮件 / Webhook 告警（"重大事件时通知我"）
- 历史相似事件匹配（"上次 BoJ 加息后 24h 走势"）
- 回测：规则准确率统计（"BoJ 加息 → USD/JPY ↓"的历史命中率）
- PWA 离线缓存
- 多用户 + 鉴权（如果要开放）

---

## 4. 系统架构

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       前端 (React + deck.gl)                            │
│   ┌─────────────┐  ┌──────────────────┐  ┌───────────────────────┐     │
│   │  News Feed  │  │  Map + ArcLayer  │  │  Asset Impact Cards   │     │
│   └─────────────┘  └──────────────────┘  └───────────────────────┘     │
│                       Zustand store ← WebSocket                          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ WSS / HTTPS
┌────────────────────────────────────▼────────────────────────────────────┐
│                  后端 (Python 3.13 + FastAPI)                           │
│                                                                          │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────────┐     │
│  │ Ingestion    │──▶│ Event Pipeline   │──▶│  WebSocket Hub      │     │
│  │ (APScheduler)│   │  • Classify      │   │  (broadcast)        │     │
│  │              │   │  • Rule match    │   │                     │     │
│  │ • RSS feeds  │   │  • LLM fallback  │   └─────────────────────┘     │
│  │ • Binance WS │   │  • Compute       │            ▲                  │
│  │ • AKShare    │   │    impact        │            │                  │
│  │ • FRED       │   └────────┬─────────┘            │                  │
│  │ • GDELT      │            │                      │                  │
│  └──────────────┘            ▼                      │                  │
│                       ┌──────────────┐              │                  │
│                       │  Redis       │──────────────┘                  │
│                       │  Pub/Sub     │  (events.* / prices.*)          │
│                       │  + cache     │                                  │
│                       └──────────────┘                                  │
│                              │                                          │
│                              ▼                                          │
│                       ┌──────────────────────┐                          │
│                       │  PostgreSQL 16       │                          │
│                       │  + TimescaleDB       │                          │
│                       │                      │                          │
│                       │  • events            │                          │
│                       │  • assets            │                          │
│                       │  • impacts           │                          │
│                       │  • prices (hyper)    │                          │
│                       └──────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流（一个事件的完整生命周期）

```
[1] 14:30:00  APScheduler 定时拉 BoJ RSS
[2] 14:30:01  fetcher 拿到新条目 → 去重（Redis SET）→ 写入 raw_news
[3] 14:30:01  pipeline: classify_importance() → 高
[4] 14:30:02  rule_engine.match("BoJ rate hike") → 命中 rule_id=boj_rate_hike
              → 生成 Event{location=JP, severity=high}
              → 生成 N 条 ImpactPrediction{asset, direction, confidence}
[5] 14:30:02  Redis publish events.new → WS Hub
[6] 14:30:02  WS Hub broadcast 给所有在线浏览器
[7] 14:30:02  前端收到 → 地图动画 / 右栏卡片入场 / 显示"预期方向"
[8] 14:30:03  pipeline 启动 price_watcher：订阅相关资产 5 分钟价格变动
[9] 14:30:08  USD/JPY 跌 0.5% → Redis publish prices.update
[10] 14:30:08 WS Hub broadcast → 前端卡片更新"实际方向"
[11] 14:35:00 5 分钟窗口结束 → 计算最终"预期 vs 实际"准确度 → 入库
```

### 4.3 核心服务模块

| 模块 | 职责 | 关键依赖 |
|---|---|---|
| `ingestion/` | 各源的数据采集器 | `feedparser`, `httpx`, `websockets`, `akshare` |
| `pipeline/` | 事件分类 + 影响计算 | `anthropic`, 自研规则引擎 |
| `rules/` | YAML/JSON 规则定义 + matcher | 自研 |
| `storage/` | 数据库 / 缓存抽象 | `asyncpg`, `redis-py` |
| `ws/` | WebSocket Hub | `fastapi`, `websockets` |
| `api/` | REST 端点（历史、配置等） | `fastapi` |
| `models/` | Pydantic schemas | `pydantic` |

---

## 5. 数据源清单（精选）

### 5.1 新闻（事件源）

| 源 | 类型 | 拉取方式 | 频率 |
|---|---|---|---|
| Fed FOMC + 主席讲话 | RSS | `feedparser` | 5 min |
| ECB Press Releases | RSS | `feedparser` | 5 min |
| BoJ Statements | RSS | `feedparser` | 5 min |
| BoE Monetary Policy | RSS | `feedparser` | 5 min |
| PBoC（人行） | Web scrape (无 RSS) | `httpx + bs4` | 10 min |
| Reuters Business | RSS | `feedparser` | 2 min |
| Financial Times | RSS | `feedparser` | 2 min |
| GDELT Events (P1) | API | `httpx` | 15 min |
| FRED 数据 (P1) | API | `httpx` | 按事件触发 |

### 5.2 行情（资产价格）

| 源 | 覆盖 | 协议 | 备注 |
|---|---|---|---|
| **Binance WebSocket** | 加密货币 全品种 | WS Stream | 毫秒级、零成本 |
| **Binance Stocks** | 5000+ 代币化美股 | WS Stream | 毫秒级 |
| **AKShare** | A股、港股、外汇、期货、债券、中国宏观 | Python lib | 1 分钟轮询 |
| **FRED API** | 美债收益率、美国宏观指标 | REST | 按需 |

### 5.3 初始覆盖资产（约 50 个）

**外汇 (10)**: USD/JPY, EUR/USD, GBP/USD, USD/CNH, AUD/JPY, EUR/JPY, USD/CHF, USD/CAD, NZD/USD, EUR/GBP

**股指 (10)**: 标普 500, 纳斯达克, 道琼斯, 日经 225, 上证综指, 沪深 300, 恒生, 德国 DAX, 法国 CAC40, 富时 100

**债券 (5)**: 美债 10Y, 美债 2Y, 德债 10Y, 日债 10Y, 中国 10Y

**商品 (8)**: 布伦特原油, WTI, 黄金, 白银, 铜, 天然气, 玉米, 大豆

**加密 (8)**: BTC, ETH, BNB, SOL, XRP, USDT/USD, ETH/BTC, BTC.D（市占率）

**美股代表 (10)**: SPY, QQQ, AAPL, MSFT, NVDA, TSLA, JPM, XOM, GLD (黄金 ETF), TLT (长债 ETF)

---

## 6. 核心引擎设计

### 6.1 规则引擎

**目的**：用 YAML/JSON 描述"X 类型事件发生 → 影响 Y 资产，方向 Z"，覆盖 80% 高频场景，命中即用，零延迟。

**规则 schema** (`rules/boj_rate_hike.yaml`):

```yaml
id: boj_rate_hike
name: 日本央行加息
description: BoJ 上调政策利率
priority: 100

trigger:
  source: ["BoJ"]
  keywords_all: ["policy rate", "hike"]    # 必须全部命中
  keywords_any: ["increase", "raise", "上调"]  # 任一命中
  keywords_none: ["maintain", "unchanged"]  # 必须都不命中
  severity: high

origin:
  country: JP
  lat: 35.6762
  lng: 139.6503

# 触发后批量影响这些经济 region 的所有相关资产（可选）
affected_regions:
  - g7        # 日本是 G7 成员，加息事件冲击全 G7 风险资产

impacts:
  - asset: USD/JPY
    direction: down
    magnitude: medium      # small / medium / large
    rationale: 利差扩大利好日元
    timeframe_minutes: 60

  - asset: NIKKEI225
    direction: down
    magnitude: medium
    rationale: 紧缩压制风险资产 + 出口股汇率冲击
    timeframe_minutes: 120

  - asset: US10Y
    direction: up
    magnitude: small
    rationale: 套息交易反转 → 美债被抛售
    timeframe_minutes: 120

  - asset: AUD/JPY
    direction: down
    magnitude: medium
    rationale: 套息平仓
    timeframe_minutes: 60
```

**匹配算法**：
```python
def match(news_item: NewsItem) -> Optional[Rule]:
    # 按 priority 倒序遍历所有规则
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.trigger.source and news_item.source not in rule.trigger.source:
            continue
        if not all(kw in news_item.text for kw in rule.trigger.keywords_all):
            continue
        if rule.trigger.keywords_any and not any(kw in news_item.text for kw in rule.trigger.keywords_any):
            continue
        if any(kw in news_item.text for kw in rule.trigger.keywords_none or []):
            continue
        return rule
    return None
```

**初始规则集**（P0 写 ~20 条覆盖）：
- 6 大央行加/降息（12 条）
- 美国 CPI / NFP / GDP / PMI 公布（4 条）
- 中国 LPR / 社融 / CPI（3 条）
- 地缘：中东冲突升级、台海紧张、俄乌新进展（自定义匹配）

### 6.2 LLM 兜底分析

**目的**：规则未命中时，让 Claude 输出结构化的影响预测。

**Prompt 模板**:

```
你是宏观市场分析师。给定一条新闻，输出 JSON：
{
  "is_market_relevant": bool,
  "severity": "low" | "medium" | "high",
  "origin_country_iso2": "JP",
  "explanation": "1 句话解释这条新闻为何重要",
  "impacts": [
    {
      "asset_id": "USD/JPY",
      "direction": "up" | "down" | "neutral",
      "magnitude": "small" | "medium" | "large",
      "confidence": 0.0-1.0,
      "rationale": "为什么"
    }
  ]
}

可选资产列表（必须从中选）：[...50 个 asset_id...]

新闻：
"{news_text}"

约束：
- impacts 数组最多 8 个最相关资产
- 不相关市场（如本地体育新闻）→ is_market_relevant: false，impacts: []
- 用 Claude prompt caching：资产列表作为 cached 系统提示
```

**模型选择**：`claude-haiku-4-5-20251001`（便宜 + 快），仅高严重度新闻升级到 Sonnet。

**成本控制**：
- 资产列表静态 → prompt caching（90% 折扣）
- 5 分钟去重缓存（相似新闻只调一次）
- 估算：日均 200 次调用 × $0.001 = $0.2/天

### 6.3 实际 vs 预期对照

事件触发后，pipeline 启动 `price_watcher(event_id, assets, window=300s)`：
- 记录 t0 价格
- 窗口结束记录 t1 价格
- 计算 `actual_direction`、`actual_pct`
- 与 predicted_direction 对比 → `accuracy: hit | miss | partial`
- 入库 `impact_outcomes` 表，用于长期规则准确率统计

---

## 7. 数据模型

### 7.1 表结构（PostgreSQL）

```sql
-- 资产主表
CREATE TABLE assets (
    id            TEXT PRIMARY KEY,           -- "USD/JPY"
    asset_class   TEXT NOT NULL,              -- fx | equity | bond | commodity | crypto
    display_name  TEXT NOT NULL,
    country_iso   CHAR(2),                    -- 主要发行/归属国 ISO 3166-1 alpha-2
    region        TEXT,                       -- "JP" / "Global"（与 country_iso 互补）
    lat           DOUBLE PRECISION,           -- for map
    lng           DOUBLE PRECISION,
    binance_symbol TEXT,                      -- "USDJPY" if available
    akshare_func  TEXT,                       -- function name to call
    fred_series   TEXT,                       -- FRED series id
    metadata      JSONB
);

-- 经济 region（双轨制的"逻辑"轨）
CREATE TABLE economic_regions (
    id              TEXT PRIMARY KEY,         -- "eurozone" / "opec_plus" / "g7"
    label_zh        TEXT NOT NULL,            -- "欧元区"
    label_en        TEXT NOT NULL,            -- "Eurozone"
    region_type     TEXT NOT NULL,            -- monetary_union | economic_bloc | commodity_alliance
    central_bank    TEXT,                     -- "ECB" (nullable)
    metadata        JSONB                     -- 颜色、图标、描述等
);

-- 国家 ↔ 经济 region 关联（多对多）
CREATE TABLE country_economic_memberships (
    country_iso     CHAR(2) NOT NULL,
    region_id       TEXT NOT NULL REFERENCES economic_regions(id),
    joined_at       DATE,                     -- 加入时间（如比利时加入欧元区 1999-01-01）
    PRIMARY KEY (country_iso, region_id)
);
CREATE INDEX idx_membership_region ON country_economic_memberships(region_id);

-- 新闻原始入库（去重前）
CREATE TABLE raw_news (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,
    url           TEXT UNIQUE,                -- 去重键
    title         TEXT NOT NULL,
    body          TEXT,
    published_at  TIMESTAMPTZ NOT NULL,
    fetched_at    TIMESTAMPTZ DEFAULT NOW(),
    lang          TEXT
);

-- 事件（经过分析后的"重要"新闻）
CREATE TABLE events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_news_id    BIGINT REFERENCES raw_news(id),
    rule_id        TEXT,                      -- NULL if LLM-derived
    classifier     TEXT NOT NULL,             -- "rule" | "llm"
    severity       TEXT NOT NULL,             -- low | medium | high
    origin_country TEXT,                      -- ISO2
    origin_lat     DOUBLE PRECISION,
    origin_lng     DOUBLE PRECISION,
    affected_regions TEXT[],                  -- 经济 region id 数组，如 ['eurozone','g7']（可空）
    title          TEXT NOT NULL,
    explanation    TEXT,
    occurred_at    TIMESTAMPTZ NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX idx_events_regions ON events USING GIN(affected_regions);

-- 影响预测（一个事件 → N 条预测）
CREATE TABLE impact_predictions (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID REFERENCES events(id) ON DELETE CASCADE,
    asset_id        TEXT REFERENCES assets(id),
    direction       TEXT NOT NULL,            -- up | down | neutral
    magnitude       TEXT NOT NULL,            -- small | medium | large
    confidence      REAL,                     -- 0–1
    rationale       TEXT,
    timeframe_min   INT NOT NULL DEFAULT 60
);
CREATE INDEX idx_impact_event ON impact_predictions(event_id);

-- 实际结果（预测窗口结束后入库）
CREATE TABLE impact_outcomes (
    prediction_id   BIGINT PRIMARY KEY REFERENCES impact_predictions(id) ON DELETE CASCADE,
    t0_price        NUMERIC,
    t1_price        NUMERIC,
    actual_pct      REAL,
    actual_direction TEXT,                    -- up | down | flat
    accuracy        TEXT,                     -- hit | miss | partial
    computed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 价格时序（TimescaleDB 超表）
CREATE TABLE prices (
    asset_id    TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    price       NUMERIC NOT NULL,
    source      TEXT NOT NULL,                -- binance | akshare | fred
    PRIMARY KEY (asset_id, ts)
);
SELECT create_hypertable('prices', 'ts');
```

### 7.2 Redis Key 设计

| Key | 类型 | 用途 |
|---|---|---|
| `dedup:news:{sha256_url}` | SET, TTL 7d | 新闻去重 |
| `dedup:llm:{sha256_text}` | STRING, TTL 5m | LLM 调用去重缓存 |
| `price:latest:{asset_id}` | HASH | 最新价格快照（前端首屏拉取） |
| `events.new` | Pub/Sub channel | 新事件广播 |
| `prices.update` | Pub/Sub channel | 价格更新广播 |
| `ws:clients:count` | STRING | 当前在线连接数 |
| `rate:llm:minute` | STRING + EXPIRE | LLM 调用限流 |

---

## 8. API & WebSocket 协议

### 8.1 REST 端点

```
GET  /api/health                          → { status: "ok" }
GET  /api/events?since=ISO&limit=50       → [Event...]
GET  /api/events/{id}                     → Event with impacts + outcomes
GET  /api/assets                          → [Asset...]
GET  /api/assets/{id}/prices?window=24h   → [PricePoint...]
GET  /api/rules                           → [Rule...] (用于可视化编辑器 P1)
POST /api/rules                           → 新增规则 (P1)
```

### 8.2 WebSocket 协议

**连接**：`wss://host/ws`

**消息格式**：所有消息都是 JSON，带 `type` 字段。

**客户端 → 服务端**:
```json
{ "type": "subscribe", "channels": ["events", "prices"] }
{ "type": "ping" }
```

**服务端 → 客户端**:
```json
// 新事件
{
  "type": "event.new",
  "event": {
    "id": "uuid",
    "title": "BoJ raises policy rate to 0.5%",
    "severity": "high",
    "origin": { "country": "JP", "lat": 35.68, "lng": 139.65 },
    "occurred_at": "2026-06-08T14:30:00Z",
    "explanation": "...",
    "predictions": [
      { "asset_id": "USD/JPY", "direction": "down", "magnitude": "medium",
        "confidence": 0.9, "rationale": "..." }
    ]
  }
}

// 价格更新（节流后批量推送）
{
  "type": "price.update",
  "ts": "2026-06-08T14:30:08Z",
  "updates": [
    { "asset_id": "USD/JPY", "price": 148.32, "pct_1m": -0.42 },
    { "asset_id": "NIKKEI225", "price": 38450.0, "pct_1m": -0.85 }
  ]
}

// 影响结果就绪
{
  "type": "impact.outcome",
  "event_id": "uuid",
  "outcomes": [
    { "prediction_id": 123, "actual_direction": "down",
      "actual_pct": -1.2, "accuracy": "hit" }
  ]
}

// 心跳
{ "type": "pong" }
```

**节流策略**：
- 价格更新合并 200ms 内的所有更新批量发送
- 事件即时推送（不节流）

---

## 9. 技术栈（最终确认）

### 前端
- React 19 + TypeScript 5
- Vite 6
- deck.gl + MapLibre GL JS（ArcLayer + IconLayer）
- Zustand（全局状态）
- TanStack Query（REST 缓存）
- Tailwind CSS 4
- visx（sparkline）
- Framer Motion（入场动画）
- 包管理：**pnpm**

### 后端
- Python 3.13 + FastAPI
- uvicorn + uvloop
- httpx (async)
- feedparser
- akshare
- python-binance（WS 客户端）
- anthropic SDK
- APScheduler
- asyncpg（Postgres）
- redis-py
- 包管理：**uv**

### 数据 / 中间件
- PostgreSQL 16 + TimescaleDB 2
- Redis 7
- 安装方式：**原生 apt**

### 开发工具
- ruff + black（Python lint/format）
- biome（TS lint/format，更快的 ESLint+Prettier 替代）
- pytest（后端测试）
- vitest（前端测试）

---

## 10. 开发路线图

### Phase 0 —— 环境与脚手架（1 天）
- [ ] 装 uv / pnpm / postgres / timescaledb / redis
- [ ] 初始化目录结构、git、CI（GitHub Actions 跑 lint）
- [ ] Docker Compose 起服务（备选，原生为主）
- [ ] 基础健康检查端点 + 前端 hello world

### Phase 0.5 —— 地图模块抽取与边界覆盖（2 天）⭐ 新增
- [ ] 从 worldmonitor 抽取 4 个核心文件到 `frontend/src/vendor/worldmonitor-map/`：
  - `public/data/countries.geojson`（~210 KB，国家级 ADM0 多边形）
  - `public/data/country-boundary-overrides.geojson`（高精度修订）
  - `src/services/country-geometry.ts`（point-in-polygon 命中算法）
  - `src/utils/country-codes.ts`（ISO 代码工具）
- [ ] 文件头加 AGPL attribution 注释（保留原作者信息）
- [ ] 创建部署区域边界覆盖文件 `boundary-overrides.geojson`，按目标部署区域调整国家几何
- [ ] 写 `economic-regions.ts` 配置（6 个 P0 经济 region 的 country_iso 成员表）
- [ ] 把 economic_regions + memberships 数据 seed 入库
- [ ] 单元测试：`getCountryAtCoordinates(...)` 命中正确、边界覆盖按预期生效

### Phase 1 —— 数据管道（3–4 天）
- [ ] Postgres 表 + migration
- [ ] Redis 接入
- [ ] 拉 5 个央行 RSS + 入库
- [ ] Binance WS 订阅 BTC/ETH/USDJPY（代币化）+ 价格落库
- [ ] AKShare 拉 上证、恒生、USDCNH

### Phase 2 —— 事件分析（3–4 天）
- [ ] 规则引擎 + 20 条初始规则
- [ ] LLM 兜底（Anthropic SDK + caching）
- [ ] impact_predictions 入库

### Phase 3 —— 实时推送（2–3 天）
- [ ] WebSocket Hub + Redis Pub/Sub
- [ ] 节流 + 重连 + 心跳
- [ ] 前端 WS 客户端 + Zustand 接入

### Phase 4 —— UI（4–5 天）
- [ ] 三栏布局 + 主题
- [ ] 新闻流组件
- [ ] 地图 + ArcLayer 动画
- [ ] 资产卡片（预期 vs 实际）

### Phase 5 —— 历史 & 准确率（2 天）
- [ ] price_watcher 窗口任务
- [ ] impact_outcomes 计算
- [ ] 历史回看时间轴

**MVP 总计：~ 2.5 周（全职估算）**

---

## 11. 风险与未决问题

| # | 风险 / 问题 | 缓解 |
|---|---|---|
| 1 | LLM 误判产生大量假预测 | 设 confidence 阈值（< 0.6 不推前端）；每周回看准确率 |
| 2 | AKShare 偶发抓取失败 | 失败重试 + 降级到日线数据 + 标记数据陈旧 |
| 3 | Binance 代币化股票 != 原生美股，价格可能微偏 | 显示数据源标签；用户知情 |
| 4 | RSS 源延迟（有些央行 5–10 分钟才出 RSS） | Phase 2 后考虑接 WebSocket 新闻源（如 Twitter API） |
| 5 | 单台 VPS 故障 | MVP 阶段先接受；后期可加 Cloudflare Tunnel + 监控 |
| 6 | 中国大陆访问 Anthropic API 受限 | 后端在境外 VPS（您当前 VPS 已在境外 ✅）；前端通过后端代理 |
| 7 | 历史价格回看的数据存储增长 | TimescaleDB 自动分区 + 1 年后降采样到 1 小时 |
| 8 | **AGPL 合规风险**：网络部署须公开全部源码 | 项目从 day-1 在 GitHub 公开仓库；不引入闭源依赖；新成员入项目前明示协议 |
| 9 | **worldmonitor upstream 更新跟踪**：抽取的地图文件若 upstream 修 bug，我们要不要同步？ | 手动 cherry-pick 策略，每季度评估一次；优先采纳 bug fix，拒绝功能性变更 |
| 10 | **部署区域边界覆盖正确性** | 上线前由 maintainer 人工目视审查 + 自动化测试覆盖关键命中断言 |
| 11 | **经济 region 数据时效性**：成员国变化（如英国脱欧、新国入欧元区） | `country_economic_memberships.joined_at` 字段支持时间维度；定期人工 review |

---

## 12. 项目命名（已确定）

**最终名称：Aether（以太）**

| 维度 | 决策 |
|---|---|
| 项目正式名 | `Aether` |
| 中文名 | `以太` |
| GitHub repo（建议） | `aether` 或 `aether-app` |
| Python 包名 | `aether` |
| 前端包名 | `aether-frontend` |
| 数据库名 | `aether` |
| 数据库用户 | `aether` |
| 工作目录 | `/home/code/aether/` |

**命名理由**：古典物理"以太"代表"光与电磁波传播的不可见媒介"。本项目把全球金融市场视为金融以太，宏观事件如波在其中传导 —— Aether 让这种传导可视化。该隐喻贯穿产品命名、UI 文案、动画设计（弧线即"以太波纹"）。

---

## 13. 地图模块策略（路径 3：抽取 + 合规化）

### 13.1 抽取范围

从 worldmonitor 仓库精确抽取以下 **4 个文件**（约 240 KB 代码 + 数据），不引入其余 3978 个文件：

| 源路径（worldmonitor） | 目标路径（Aether） | 大小 | 用途 |
|---|---|---|---|
| `public/data/countries.geojson` | `frontend/public/vendor/worldmonitor/countries.geojson` | ~210 KB | ADM0 国家多边形 |
| `public/data/country-boundary-overrides.geojson` | `frontend/public/vendor/worldmonitor/country-boundary-overrides.geojson` | ~46 KB | 高精度边界修订 |
| `src/services/country-geometry.ts` | `frontend/src/vendor/worldmonitor/country-geometry.ts` | ~14 KB | point-in-polygon 命中算法 |
| `src/utils/country-codes.ts` | `frontend/src/vendor/worldmonitor/country-codes.ts` | ~8 KB | ISO 代码工具函数 |

**未抽取**（因为太重 / 与我们框架不兼容 / 是其领域特有）：
- `src/components/DeckGLMap.ts`（300 KB，vanilla TS，含 56 个图层逻辑）→ 我们用 React + deck.gl 自己写
- `src/components/GlobeMap.ts`（157 KB）→ 我们不要 3D 球
- 56 个图层定义、Convex 后端代码、Tauri 集成、变体系统、i18n 等

### 13.2 Vendor 策略

抽取的文件放在专门的 vendor 目录隔离，**严禁**业务代码直接修改 vendor 文件：

```
frontend/
├── src/
│   ├── vendor/
│   │   └── worldmonitor/
│   │       ├── LICENSE                   ← AGPL-3.0 副本
│   │       ├── ATTRIBUTION.md            ← 注明来源、commit hash、抽取日期
│   │       ├── country-geometry.ts       ← 原文件，头部加 AGPL 注释
│   │       └── country-codes.ts
│   └── features/map/
│       ├── WorldMap.tsx                  ← 我们自己写的 React 组件
│       └── useCountryHitTest.ts          ← 包装 vendor 函数为 React hook
└── public/vendor/worldmonitor/
    ├── countries.geojson
    └── country-boundary-overrides.geojson
```

**抽取文件的头部注释模板**：
```typescript
/**
 * SOURCE: https://github.com/koala73/worldmonitor
 * COMMIT: <抽取时的 commit hash>
 * DATE:   <抽取日期>
 * LICENSE: AGPL-3.0-only (see ./LICENSE)
 *
 * Original author: @koala73
 * Modifications by World Info contributors (see git history).
 */
```

### 13.3 部署区域边界覆盖

对于不同部署区域，国家边界的呈现可能需要与上游 Natural Earth / worldmonitor 数据有所不同。Aether 通过一个额外的 GeoJSON 覆盖文件 `frontend/public/data/boundary-overrides.geojson` 支持此场景。该文件由各部署 maintainer 自行维护，加载时享有最高优先级。

**加载顺序**：

```typescript
// frontend/src/features/map/loadGeometry.ts
const base = await load("/vendor/worldmonitor/countries.geojson");
const wmOverrides = await load("/vendor/worldmonitor/country-boundary-overrides.geojson");
const localOverrides = await load("/data/boundary-overrides.geojson");

// 后加载的覆盖前面的，本地 overrides 拥有最高优先级
const finalGeometry = applyOverrides(base, [wmOverrides, localOverrides]);
```

**验收方式**：
- 上线前由 maintainer 目视审查 `boundary-overrides.geojson` 的内容
- 单元测试覆盖关键坐标的命中断言（由部署 maintainer 按目标区域要求编写）

### 13.4 与 deck.gl 的集成

抽取的 `country-geometry.ts` 是纯算法（point-in-polygon + 索引），跟具体地图库无关。我们的 React 组件用法：

```typescript
// frontend/src/features/map/WorldMap.tsx
import { GeoJsonLayer } from "@deck.gl/layers";
import { getCountryAtCoordinates } from "@/vendor/worldmonitor/country-geometry";
import { Map as MapLibreMap } from "react-map-gl/maplibre";
import { DeckGL } from "@deck.gl/react";

const countriesLayer = new GeoJsonLayer({
  id: "countries",
  data: finalGeometry,
  pickable: true,
  stroked: true,
  filled: true,
  getFillColor: (f) => getCountryFillColor(f.properties.ISO_A2),
  onClick: (info) => onCountryClick(info.object.properties.ISO_A2),
});
```

---

## 14. 经济 region 双轨体系

### 14.1 设计哲学

- **地理 region**（PolyWorld/worldmonitor 都用的）：纯视觉分区，用于"快速导航 + 视角预设"
- **经济 region**（我们独有）：按金融逻辑分组，用于"事件传导 + 资产联动"

**两者正交**：一个事件可以同时影响"地理上的亚太" + "经济上的 G7"。

### 14.2 P0 经济 region 清单（6 个）

| ID | 中文名 | 类型 | 成员 ISO（示例） | 主要联动资产 |
|---|---|---|---|---|
| `eurozone` | 欧元区 | monetary_union | DE, FR, IT, ES, NL, BE, AT, PT, FI, IE, GR, LU, CY, MT, SK, SI, EE, LV, LT, HR | DAX, CAC40, EUR/USD, Bund10Y |
| `g7` | G7 | economic_bloc | US, JP, DE, GB, FR, IT, CA | SPX, NIKKEI, DAX, USD/JPY |
| `g20` | G20 | economic_bloc | G7 + CN, IN, BR, RU, AU, KR, ID, MX, TR, SA, ZA, AR + EU | 全球主要风险资产 |
| `opec_plus` | OPEC+ | commodity_alliance | SA, AE, IQ, IR, KW, VE, NG, DZ, AO, RU, MX, KZ, OM, ... | BRENT, WTI, USD/SAR |
| `brics` | BRICS | economic_bloc | BR, RU, IN, CN, ZA + IR, AE, EG, ET（2024 扩员） | 各国主要股指 + 货币 |
| `asean` | ASEAN | economic_bloc | ID, TH, SG, MY, PH, VN, MM, KH, LA, BN | 东南亚股指 + 货币 |

### 14.3 数据结构（已在 §7.1 落表）

```sql
economic_regions(id, label_zh, label_en, region_type, central_bank, metadata)
country_economic_memberships(country_iso, region_id, joined_at)
events.affected_regions TEXT[]    -- 新增字段
assets.country_iso CHAR(2)        -- 新增字段
```

### 14.4 触发与可视化

**触发路径**：规则 / LLM 输出事件时填写 `affected_regions: ["g7"]` → backend 解析 → 查询该 region 所有成员国 ISO → 一并在 `events.origin_country` 周边批量高亮成员国 → 弧线从震源辐射到所有成员国。

**前端表现**：
- 顶部增加一行 chip：`[🇪🇺 欧元区] [G7] [G20] [OPEC+] [BRICS] [ASEAN]`，点击 toggle 高亮
- 单选 chip 时：地图上该 region 所有成员国浅染色，右栏只显示该 region 的相关资产
- 事件入场动画：若事件 `affected_regions` 非空，弧线同时射向所有成员国

### 14.5 扩展（P1+）

- 加入更多 region：欧盟（27 国，区别于欧元区 20 国）、GCC（海合会 6 国）、CPTPP、SCO（上合）、AU（非盟）
- 用户自定义 region（"我的关注 region"，存 localStorage）
- 时间维度查询（"2010 年欧元区有哪些国家" vs 现在）
