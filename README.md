# Aether · 以太

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

> **Watch macro events propagate through the global financial aether.**
> 全球金融市场是一片"以太"，宏观事件如同波在其中穿透传导。Aether 让这种看不见的传导**变得肉眼可见**。

**典型场景**：日央行加息 → 地图日本亮起 → 弧线如波穿越以太射向美国 / 欧洲 / 澳洲 → 右侧资产卡片同步显示 USD/JPY、日经、美债的"预期方向 vs 实际涨跌"。

详细产品 / 技术设计：见 [`PROJECT_DESIGN.md`](./PROJECT_DESIGN.md)
开发协作约定（给 Claude Code 用）：见 [`CLAUDE.md`](./CLAUDE.md)

---

## 技术栈

- **前端**：React 19 + TypeScript + Vite + deck.gl + MapLibre GL + Zustand + TanStack Query + Tailwind CSS
- **后端**：Python 3.13 + FastAPI + asyncpg + redis-py + APScheduler + Anthropic SDK
- **数据**：PostgreSQL 16 + TimescaleDB + Redis 7
- **行情源**：Binance WebSocket（加密 + 代币化美股）+ AKShare（A 股/港股/外汇/期货/中国宏观）+ FRED（美债 / 美国宏观）
- **新闻源**：5 大央行 RSS + Reuters + FT + GDELT（地缘事件）

---

## 环境要求

- Ubuntu 22.04 LTS 或同等 Linux
- Python 3.13+
- Node.js 22+ LTS
- PostgreSQL 16 + TimescaleDB 2
- Redis 7+
- 最低 2 vCPU / 4 GB RAM / 20 GB 磁盘（推荐 3+ vCPU / 8 GB RAM）

---

## 一次性安装（首次开发前）

```bash
# 1. 系统依赖（apt）
sudo apt update
sudo apt install -y postgresql-16 postgresql-16-timescaledb redis-server

# 2. uv（Python 包管理，10× pip 速度）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. pnpm（前端包管理）
npm i -g pnpm

# 4. 启动服务并启用 TimescaleDB
sudo systemctl enable --now postgresql redis-server
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 5. 创建数据库与用户
sudo -u postgres createdb aether
sudo -u postgres psql -c "CREATE USER aether WITH PASSWORD 'changeme';"
sudo -u postgres psql -c "GRANT ALL ON DATABASE aether TO aether;"
```

---

## 运行

### 后端

```bash
cd backend
uv sync                                  # 安装依赖
cp .env.example .env                     # 填 ANTHROPIC_API_KEY / DB_URL / REDIS_URL
uv run alembic upgrade head              # 数据库 migration
uv run python scripts/seed-assets.py     # 灌初始资产数据
uv run uvicorn src.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev                                 # http://localhost:5173
```

### 同时启动（开发体验）

```bash
# 项目根目录
pnpm dlx concurrently \
  "cd backend && uv run uvicorn src.main:app --reload" \
  "cd frontend && pnpm dev"
```

---

## 测试

```bash
# 后端
cd backend && uv run pytest

# 前端
cd frontend && pnpm test
```

---

## Lint / Format

```bash
# 后端
cd backend && uv run ruff check . && uv run ruff format .

# 前端
cd frontend && pnpm biome check --write .
```

---

## 项目状态

⏳ 当前处于**设计阶段**，尚未开始编码。已完成设计文档（`PROJECT_DESIGN.md`、`CLAUDE.md`、本 README），等待 Phase 0 脚手架搭建。

---

## License

本项目采用 **[GNU AGPL-3.0-only](https://www.gnu.org/licenses/agpl-3.0)**。

这意味着任何使用本项目代码的网络服务（包括 SaaS / 在线 dashboard），必须向所有用户提供**完整源代码**，包括您新增的任何修改。详情见 [LICENSE](./LICENSE)。

**为什么是 AGPL**：Aether 从 [worldmonitor](https://github.com/koala73/worldmonitor)（AGPL-3.0-only）抽取核心地图模块（4 个文件，约 240 KB），按 AGPL 传染性条款，整个项目须以 AGPL 发布。

详见 [`PROJECT_DESIGN.md` §0](./PROJECT_DESIGN.md) 与 [`§13`](./PROJECT_DESIGN.md)。

---

## 致谢

Aether 站在以下开源工作的肩膀上：

- **[worldmonitor](https://worldmonitor.app)** by [@koala73](https://github.com/koala73)
  地图分块与国家几何命中算法的直接代码来源（vendored，AGPL-3.0-only）
- **[PolyWorld](https://github.com/AmazingAng/PolyWorld)** by [@AmazingAng](https://github.com/AmazingAng)
  UI 布局与脉冲动画模式的设计参考（不含代码拷贝，MIT-licensed inspiration）
- **[Natural Earth](https://www.naturalearthdata.com/)** — 国家边界基础数据（Public Domain）
- **[deck.gl](https://deck.gl/)**, **[MapLibre GL JS](https://maplibre.org/)** — 地图渲染库
- **[AKShare](https://github.com/akfamily/akshare)** — 中国金融数据接口
- **[Binance API](https://binance-docs.github.io/apidocs/)** — 加密与代币化股票实时行情

---

## 合规声明（重要）

Aether 严格遵循中华人民共和国国家测绘局发布的官方版图：

- 台湾、香港、澳门为中华人民共和国领土
- 藏南地区（含所谓"阿鲁纳恰尔邦"）、阿克塞钦属中华人民共和国
- 钓鱼岛及其附属岛屿属中华人民共和国
- 南海九段线（U 形线）内岛礁及水域属中华人民共和国

具体实现见 `frontend/public/data/china-compliance-overrides.geojson`，加载时强制覆盖上游 worldmonitor / Natural Earth 的对应几何。

**部署到生产环境前**，必须通过 `pnpm test -- --grep "china-compliance"` 所有断言。详见 [`PROJECT_DESIGN.md` §13.3](./PROJECT_DESIGN.md)。
