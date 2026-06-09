"""Economic region and country-membership models.

An economic region is a logical grouping of countries with shared market
characteristics (Eurozone, G7, OPEC+, ...). When a macro event impacts a
region, the event's effects fan out to all member countries.
"""

from datetime import date

from sqlalchemy import CHAR, JSON, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aether.models.base import Base


class EconomicRegion(Base):
    __tablename__ = "economic_regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label_zh: Mapped[str] = mapped_column(String(64), nullable=False)
    label_en: Mapped[str] = mapped_column(String(64), nullable=False)
    region_type: Mapped[str] = mapped_column(String(32), nullable=False)
    central_bank: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extra: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    memberships: Mapped[list["CountryEconomicMembership"]] = relationship(
        back_populates="region",
        cascade="all, delete-orphan",
    )


class CountryEconomicMembership(Base):
    __tablename__ = "country_economic_memberships"

    country_iso: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("economic_regions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    joined_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    region: Mapped[EconomicRegion] = relationship(back_populates="memberships")
