"""FastAPI application entry point."""

from fastapi import FastAPI

from aether import __version__

app = FastAPI(
    title="Aether API",
    description="Macro events propagating through the global financial aether.",
    version=__version__,
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "project": "aether", "version": __version__}
