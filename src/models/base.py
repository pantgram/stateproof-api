import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SessionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    hex_root: Mapped[str] = mapped_column(String(64), server_default="0" * 64)
    leaf_hashes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    leaf_session_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True)
    tree_nodes: Mapped[list["WorkflowTreeNode"]] = relationship(back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_workflow_id", "workflow_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflows.id", ondelete="CASCADE")
    )
    session_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        default=SessionStatus.completed,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workflow: Mapped["Workflow"] = relationship(back_populates="sessions")
    event_rows: Mapped[list["Event"]] = relationship(back_populates="session", cascade="all, delete-orphan", passive_deletes=True)
    event_tree_nodes: Mapped[list["SessionTreeNode"]] = relationship(back_populates="session", cascade="all, delete-orphan", passive_deletes=True)
    workflow_leaf: Mapped["WorkflowTreeNode | None"] = relationship(
        primaryjoin="Session.id == foreign(WorkflowTreeNode.session_id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_session_id", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE")
    )
    event_hash: Mapped[str] = mapped_column(String(64))
    sequence_no: Mapped[int] = mapped_column(Integer)

    session: Mapped["Session"] = relationship(back_populates="event_rows")


class WorkflowTreeNode(Base):
    __tablename__ = "workflow_tree_nodes"
    __table_args__ = (
        Index("ix_workflow_tree_nodes_workflow_id", "workflow_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflows.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    hash: Mapped[str] = mapped_column(String(64))
    entry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    left_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    right_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    is_leaf: Mapped[bool] = mapped_column(default=False)

    workflow: Mapped["Workflow"] = relationship(back_populates="tree_nodes")


class SessionTreeNode(Base):
    __tablename__ = "session_tree_nodes"
    __table_args__ = (
        Index("ix_session_tree_nodes_session_id", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE")
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    hash: Mapped[str] = mapped_column(String(64))
    entry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    left_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    right_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    is_leaf: Mapped[bool] = mapped_column(default=False)

    session: Mapped["Session"] = relationship(back_populates="event_tree_nodes")
