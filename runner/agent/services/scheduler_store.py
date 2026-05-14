from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    cron: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(512), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SchedulerStore:
    def __init__(self, db_url: str = "sqlite:///./data/scheduler/tasks.db"):
        if db_url.startswith("sqlite:///"):
            path = Path(db_url.replace("sqlite:///", "", 1))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(db_url, future=True)
        Base.metadata.create_all(self.engine)
        self._ensure_columns()

    def _ensure_columns(self):
        columns = {column["name"] for column in inspect(self.engine).get_columns("scheduled_tasks")}
        with self.engine.begin() as conn:
            if "description" not in columns:
                conn.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN description VARCHAR(512) DEFAULT ''"))
            if "prompt" not in columns:
                conn.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN prompt TEXT DEFAULT ''"))

    def get_task(self, name: str) -> ScheduledTask | None:
        with Session(self.engine) as session:
            return session.scalar(select(ScheduledTask).where(ScheduledTask.name == name))

    def ensure_task(
        self,
        name: str,
        cron: str,
        description: str = "",
        prompt: str = "",
        payload: dict[str, Any] | None = None,
        enabled: bool = True,
        next_run: datetime | None = None,
    ) -> ScheduledTask:
        with Session(self.engine) as session:
            task = session.scalar(select(ScheduledTask).where(ScheduledTask.name == name))
            if task is None:
                task = ScheduledTask(
                    name=name,
                    cron=cron,
                    description=description,
                    prompt=prompt,
                    payload=payload or {},
                    enabled=enabled,
                    next_run=next_run,
                )
                session.add(task)
                session.commit()
                session.refresh(task)
            return task

    def upsert_task(
        self,
        name: str,
        cron: str,
        description: str | None = None,
        prompt: str | None = None,
        payload: dict[str, Any] | None = None,
        enabled: bool = True,
        next_run: datetime | None = None,
    ) -> ScheduledTask:
        with Session(self.engine) as session:
            task = session.scalar(select(ScheduledTask).where(ScheduledTask.name == name))
            if task is None:
                task = ScheduledTask(name=name, cron=cron)
                session.add(task)
            task.cron = cron
            if description is not None:
                task.description = description
            if prompt is not None:
                task.prompt = prompt
            task.payload = payload or {}
            task.enabled = enabled
            task.next_run = next_run
            session.commit()
            session.refresh(task)
            return task

    def list_enabled(self) -> list[ScheduledTask]:
        with Session(self.engine) as session:
            return list(session.scalars(select(ScheduledTask).where(ScheduledTask.enabled.is_(True))).all())

    def mark_run(self, name: str, last_run: datetime, next_run: datetime | None = None):
        with Session(self.engine) as session:
            task = session.scalar(select(ScheduledTask).where(ScheduledTask.name == name))
            if task is None:
                return
            task.last_run = last_run
            task.next_run = next_run
            session.commit()

    def update_next_run(self, name: str, next_run: datetime | None):
        with Session(self.engine) as session:
            task = session.scalar(select(ScheduledTask).where(ScheduledTask.name == name))
            if task is None:
                return
            task.next_run = next_run
            session.commit()
