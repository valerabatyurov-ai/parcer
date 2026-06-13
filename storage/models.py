from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    events: Mapped[list["EventModel"]] = relationship(back_populates="bookmaker")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sport: Mapped[str] = mapped_column(String(100), nullable=False)
    league: Mapped[str] = mapped_column(String(300), nullable=False)
    home_team: Mapped[str] = mapped_column(String(300), nullable=False)
    away_team: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_home_team: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_away_team: Mapped[str] = mapped_column(String(300), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_url: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    bookmaker: Mapped[Bookmaker] = relationship(back_populates="events")
    markets: Mapped[list["MarketModel"]] = relationship(back_populates="event")


class MarketModel(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    market_type: Mapped[str] = mapped_column(String(100), nullable=False)
    market_name: Mapped[str] = mapped_column(String(300), nullable=False)
    line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    event: Mapped[EventModel] = relationship(back_populates="markets")
    odds: Mapped[list["OddsModel"]] = relationship(back_populates="market")


class OddsModel(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False)
    outcome_name: Mapped[str] = mapped_column(String(300), nullable=False)
    side: Mapped[str] = mapped_column(String(50), nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    market: Mapped[MarketModel] = relationship(back_populates="odds")


class OddsHistory(Base):
    __tablename__ = "odds_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id"), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False)
    outcome_name: Mapped[str] = mapped_column(String(300), nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ArbitrageOpportunityModel(Base):
    __tablename__ = "arbitrage_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    sport: Mapped[str] = mapped_column(String(100), nullable=False)
    league: Mapped[str] = mapped_column(String(300), nullable=False)
    event_name: Mapped[str] = mapped_column(String(700), nullable=False)
    market_type: Mapped[str] = mapped_column(String(100), nullable=False)
    line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bookmaker_1: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome_1: Mapped[str] = mapped_column(String(300), nullable=False)
    odds_1: Mapped[float] = mapped_column(Float, nullable=False)
    bookmaker_2: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome_2: Mapped[str] = mapped_column(String(300), nullable=False)
    odds_2: Mapped[float] = mapped_column(Float, nullable=False)
    implied_sum: Mapped[float] = mapped_column(Float, nullable=False)
    profit_percent: Mapped[float] = mapped_column(Float, nullable=False)
    bankroll_rub: Mapped[float] = mapped_column(Float, nullable=False)
    stake_1: Mapped[float] = mapped_column(Float, nullable=False)
    stake_2: Mapped[float] = mapped_column(Float, nullable=False)
    expected_payout: Mapped[float] = mapped_column(Float, nullable=False)
    profit_rub: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SentNotification(Base):
    __tablename__ = "sent_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arbitrage_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    profit_percent: Mapped[float] = mapped_column(Float, nullable=False)
    odds_snapshot: Mapped[str] = mapped_column(Text, nullable=False)


class UnmatchedEvent(Base):
    __tablename__ = "unmatched_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bookmaker_1: Mapped[str] = mapped_column(String(100), nullable=False)
    event_name_1: Mapped[str] = mapped_column(String(700), nullable=False)
    bookmaker_2: Mapped[str] = mapped_column(String(100), nullable=False)
    event_name_2: Mapped[str] = mapped_column(String(700), nullable=False)
    sport: Mapped[str] = mapped_column(String(100), nullable=False)
    league: Mapped[str] = mapped_column(String(300), nullable=False)
    start_time_1: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_time_2: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_alias: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ParserErrorModel(Base):
    __tablename__ = "parser_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bookmaker: Mapped[str] = mapped_column(String(100), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
