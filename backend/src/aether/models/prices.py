"""Price time-series. Becomes a TimescaleDB hypertable in migration."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from aether.models.base import Base


class Price(Base):
    """One row per (asset, timestamp) — high-write time series."""

    __tablename__ = "prices"

    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # binance | akshare | fred
