"""Editorial workspace, independent of source ingestion and public content."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from canarias_site.db.base import Base


class StudioDocument(Base):
    __tablename__ = "cc_studio_documents"
    __table_args__ = (UniqueConstraint("kind", "island", "resource", "record_key"), {"schema": "design"})

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    island: Mapped[str] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(Text)
    record_key: Mapped[str] = mapped_column(Text)
    draft: Mapped[dict] = mapped_column(JSONB)
    published: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    base_fingerprint: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StudioRevision(Base):
    __tablename__ = "cc_studio_revisions"
    __table_args__ = (UniqueConstraint("document_id", "version"), {"schema": "design"})

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("design.cc_studio_documents.id"))
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StudioAsset(Base):
    __tablename__ = "cc_studio_assets"
    __table_args__ = {"schema":"design"}
    digest: Mapped[str] = mapped_column(Text,primary_key=True)
    mime_type: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
