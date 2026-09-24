# -*- coding: utf-8 -*-
"""SQLite 持久化模型与仓储函数。"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import DateTime, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings

settings.ensure_directories()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class KeyValue(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class WatchStock(Base):
    __tablename__ = "watchlist"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(40), default="")
    group_name: Mapped[str] = mapped_column(String(40), default="默认")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ReviewSnapshot(Base):
    __tablename__ = "review_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SavedScreener(Base):
    __tablename__ = "saved_screeners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def init_database() -> None:
    Base.metadata.create_all(engine)
    defaults = {
        "ui.theme": "dark",
        "ui.default_page": "/dashboard",
        "ui.table_density": "middle",
        "refresh.market": settings.market_refresh_seconds,
        "refresh.list": settings.list_refresh_seconds,
        "source.longhuvip.enabled": False,
    }
    with session_scope() as session:
        for key, value in defaults.items():
            if session.get(KeyValue, key) is None:
                session.add(KeyValue(key=key, value=json.dumps(value, ensure_ascii=False)))


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_settings() -> dict[str, Any]:
    with session_scope() as session:
        return {
            row.key: json.loads(row.value)
            for row in session.scalars(select(KeyValue).order_by(KeyValue.key))
        }


def patch_settings(values: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    with session_scope() as session:
        for key, value in values.items():
            row = session.get(KeyValue, key)
            encoded = json.dumps(value, ensure_ascii=False)
            if row:
                row.value = encoded
                row.updated_at = now
            else:
                session.add(KeyValue(key=key, value=encoded, updated_at=now))
    return get_settings()


def list_watchlist() -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(select(WatchStock).order_by(WatchStock.created_at)).all()
        return [
            {"code": row.code, "name": row.name, "group": row.group_name, "note": row.note}
            for row in rows
        ]


def upsert_watch(code: str, name: str = "", group: str = "默认", note: str = "") -> None:
    with session_scope() as session:
        row = session.get(WatchStock, code)
        if row:
            row.name, row.group_name, row.note = name or row.name, group, note
        else:
            session.add(WatchStock(code=code, name=name, group_name=group, note=note))


def remove_watch(code: str) -> None:
    with session_scope() as session:
        row = session.get(WatchStock, code)
        if row:
            session.delete(row)


def save_snapshot(trade_date: str, category: str, payload: Any, source: str) -> None:
    with session_scope() as session:
        session.execute(
            delete(ReviewSnapshot).where(
                ReviewSnapshot.trade_date == trade_date,
                ReviewSnapshot.category == category,
            )
        )
        session.add(
            ReviewSnapshot(
                trade_date=trade_date,
                category=category,
                payload=json.dumps(payload, ensure_ascii=False),
                source=source,
            )
        )


def get_snapshots(trade_date: str | None = None) -> list[dict[str, Any]]:
    stmt = select(ReviewSnapshot).order_by(ReviewSnapshot.trade_date.desc(), ReviewSnapshot.category)
    if trade_date:
        stmt = stmt.where(ReviewSnapshot.trade_date == trade_date)
    with session_scope() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "date": row.trade_date,
                "category": row.category,
                "data": json.loads(row.payload),
                "source": row.source,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def cleanup_snapshots(retention_days: int | None = None) -> int:
    keep_count = retention_days or settings.retention_days
    with session_scope() as session:
        dates = session.scalars(
            select(ReviewSnapshot.trade_date)
            .distinct()
            .order_by(ReviewSnapshot.trade_date.desc())
        ).all()
        if len(dates) <= keep_count:
            return 0
        cutoff = dates[keep_count - 1]
        result = session.execute(delete(ReviewSnapshot).where(ReviewSnapshot.trade_date < cutoff))
        return int(result.rowcount or 0)


def save_screener(name: str, payload: dict[str, Any]) -> None:
    with session_scope() as session:
        row = session.scalar(select(SavedScreener).where(SavedScreener.name == name))
        encoded = json.dumps(payload, ensure_ascii=False)
        if row:
            row.payload, row.updated_at = encoded, datetime.now()
        else:
            session.add(SavedScreener(name=name, payload=encoded))


def list_screeners() -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(select(SavedScreener).order_by(SavedScreener.updated_at.desc())).all()
        return [{"id": row.id, "name": row.name, **json.loads(row.payload)} for row in rows]
