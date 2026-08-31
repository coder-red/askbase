"""SQLAlchemy 2.0 ORM models for BaseChatt.

Schema covers the full knowledge store: companies, sources, documents with
versioning, sections, chunks (with pgvector embeddings), tables, financial
metrics, ingestion jobs, sync runs, citations, research sessions/steps and
evaluation records.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


# Dimension of embedding vectors. Must match the provider's embedded model.
EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


class AuthorityLevel(enum.StrEnum):
    PRIMARY_REGULATOR = "PRIMARY_REGULATOR"
    PRIMARY_EXCHANGE = "PRIMARY_EXCHANGE"
    COMPANY_PRIMARY = "COMPANY_PRIMARY"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"


class DocumentType(enum.StrEnum):
    ANNUAL_REPORT = "annual_report"
    QUARTERLY_REPORT = "quarterly_report"
    PRESS_RELEASE = "press_release"
    CIRCULAR = "circular"
    COMMUNIQUE = "communique"
    GUIDELINE = "guideline"
    STATISTICAL_BULLETIN = "statistical_bulletin"
    ECONOMIC_REPORT = "economic_report"
    FINANCIAL_STATEMENT = "financial_statement"
    INVESTOR_PRESENTATION = "investor_presentation"
    MARKET_ANNOUNCEMENT = "market_announcement"
    EARNINGS_RELEASE = "earnings_release"
    OTHER = "other"


class ProcessingStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SyncStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ChunkType(enum.StrEnum):
    TEXT = "text"
    TABLE = "table"
    HEADING = "heading"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    ngx_symbol: Mapped[str] = mapped_column(String(32), default="", index=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(64), index=True)
    ir_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list[Document]] = relationship(back_populates="company")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # cbn, nbs, ...
    name: Mapped[str] = mapped_column(String(200))
    authority_level: Mapped[AuthorityLevel] = mapped_column(
        Enum(AuthorityLevel, name="authority_level"), default=AuthorityLevel.SECONDARY
    )
    base_url: Mapped[str] = mapped_column(String(500), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    documents: Mapped[list[Document]] = relationship(back_populates="source")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(String(1000), index=True)
    external_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authority_level: Mapped[AuthorityLevel] = mapped_column(
        Enum(AuthorityLevel, name="doc_authority_level"),
        default=AuthorityLevel.SECONDARY,
        index=True,
    )
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    company: Mapped[Company | None] = relationship(back_populates="documents")
    source: Mapped[Source] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_source_company_type", "source_id", "company_id", "document_type"),
        UniqueConstraint("source_id", "external_id", name="uq_document_source_external"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    raw_path: Mapped[str] = mapped_column(String(1000), default="")
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"), default=ProcessingStatus.PENDING
    )

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_version_number"
        ),
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"), index=True
    )
    parent_section_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_sections.id"), nullable=True
    )
    number: Mapped[str] = mapped_column(String(20), default="")
    title: Mapped[str] = mapped_column(String(500))
    level: Mapped[int] = mapped_column(Integer, default=1)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"), index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_sections.id"), nullable=True
    )
    section: Mapped[str] = mapped_column(String(500), default="")
    subsection: Mapped[str] = mapped_column(String(500), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_type: Mapped[ChunkType] = mapped_column(
        Enum(ChunkType, name="chunk_type"), default=ChunkType.TEXT, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_version_type", "version_id", "chunk_type"),
    )


class TableRecord(Base):
    __tablename__ = "tables"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"), index=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(500), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    headers: Mapped[list] = mapped_column(JSON, default=list)
    rows: Mapped[list] = mapped_column(JSON, default=list)
    units: Mapped[str] = mapped_column(String(50), default="")
    currency: Mapped[str] = mapped_column(String(20), default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True
    )
    metric: Mapped[str] = mapped_column(String(200), index=True)
    value: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(20), default="NGN")
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_metrics_company_metric_period", "company_id", "metric", "period_end"),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True, index=True
    )
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True, index=True
    )
    stage: Mapped[str] = mapped_column(String(100), default="download")
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="job_status"), default=ProcessingStatus.PENDING
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_code: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status"), default=SyncStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents_discovered: Mapped[int] = mapped_column(Integer, default=0)
    documents_added: Mapped[int] = mapped_column(Integer, default=0)
    documents_updated: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id"), nullable=True
    )
    chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id"), nullable=True
    )
    section: Mapped[str] = mapped_column(String(500), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ResearchStep(Base):
    __tablename__ = "research_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(32), index=True)
    step_type: Mapped[str] = mapped_column(String(100))
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    expected_answer: Mapped[str] = mapped_column(Text, default="")
    relevant_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    relevant_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    method: Mapped[str] = mapped_column(String(50), index=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
