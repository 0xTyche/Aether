"""Asset master table — every tradable / displayable instrument we track."""

from sqlalchemy import CHAR, JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from aether.models.base import Base


class Asset(Base):
    """One row per asset shown to the user."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    country_iso: Mapped[str | None] = mapped_column(CHAR(2), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Source identifiers — exactly one should be set per asset depending on
    # which fetcher owns it.
    binance_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    akshare_func: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fred_series: Mapped[str | None] = mapped_column(String(32), nullable=True)

    extra: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
