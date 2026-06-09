# Aether

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

A real-time map of how macro events move global markets.

When a central bank moves, a geopolitical event breaks, or economic data prints,
Aether visualizes which assets are affected, where, and by how much — within seconds.

## Requirements

- Linux (Ubuntu 22.04 LTS or similar)
- Python 3.13+
- Node.js 22+
- PostgreSQL 16 with TimescaleDB 2
- Redis 6+

## Getting started

Install the toolchain:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
npm i -g pnpm
```

Set up the database:

```bash
sudo apt install -y postgresql-16 postgresql-16-timescaledb redis-server
sudo systemctl enable --now postgresql redis-server
sudo -u postgres psql -c "CREATE USER aether WITH PASSWORD 'changeme';"
sudo -u postgres createdb aether -O aether
sudo -u postgres psql -d aether -c "CREATE EXTENSION timescaledb;"
```

Run the backend:

```bash
cd backend
cp .env.example .env  # set ANTHROPIC_API_KEY
uv sync
uv run uvicorn aether.main:app --reload --port 8000
```

Run the frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Open <http://localhost:5173>.

## Documentation

See [PROJECT_DESIGN.md](./PROJECT_DESIGN.md) for architecture, data model, and design notes.

## Acknowledgements

- [worldmonitor](https://github.com/koala73/worldmonitor) — country geometry and map data (AGPL-3.0)
- [PolyWorld](https://github.com/AmazingAng/PolyWorld) — UI inspiration
- [Natural Earth](https://www.naturalearthdata.com/) — base country boundary data
- [deck.gl](https://deck.gl), [MapLibre GL JS](https://maplibre.org/), [FastAPI](https://fastapi.tiangolo.com/), [AKShare](https://github.com/akfamily/akshare)

## License

[GNU AGPL-3.0-only](./LICENSE).
