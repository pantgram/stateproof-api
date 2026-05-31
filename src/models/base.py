import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, text, Uuid
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
    leaf_hash: Mapped[str] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64))
    event_count: Mapped[int] = mapped_column(Integer, default=0)
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
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="sessions")
    tree_nodes: Mapped[list["SessionTreeNode"]] = relationship(back_populates="session", cascade="all, delete-orphan", passive_deletes=True)


class SessionTreeNode(Base):
    __tablename__ = "session_tree_nodes"
    __table_args__ = (
        Index("ix_session_tree_nodes_session_id", "session_id"),
        Index("ix_session_tree_nodes_session_id_level_position", "session_id", "level", "position"),
        Index("ix_session_tree_nodes_session_id_is_leaf", "session_id", postgresql_where=text("is_leaf = true")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE")
    )
    hash: Mapped[str] = mapped_column(String(64))
    left_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    right_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    is_leaf: Mapped[bool] = mapped_column(Boolean)
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["Session"] = relationship(back_populates="tree_nodes")


class WorkflowTreeNode(Base):
    __tablename__ = "workflow_tree_nodes"
    __table_args__ = (
        Index("ix_workflow_tree_nodes_workflow_id", "workflow_id"),
        Index("ix_workflow_tree_nodes_workflow_id_level_position", "workflow_id", "level", "position"),
        Index("ix_workflow_tree_nodes_session_id_is_leaf", "session_id", postgresql_where=text("is_leaf = true")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflows.id", ondelete="CASCADE")
    )
    hash: Mapped[str] = mapped_column(String(64))
    left_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    right_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    is_leaf: Mapped[bool] = mapped_column(Boolean)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )

    workflow: Mapped["Workflow"] = relationship(back_populates="tree_nodes")
