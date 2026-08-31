"""Data-access repositories for BaseChatt.

Repositories centralise database queries so the retrieval, ingestion, and API
layers do not embed SQL. They use async sessions and avoid N+1 patterns.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from basechatt.database.models import (
    AuthorityLevel,
    Citation,
    Company,
    Document,
    DocumentChunk,
    DocumentType,
    DocumentVersion,
    FinancialMetric,
    IngestionJob,
    ProcessingStatus,
    Source,
    SyncRun,
    SyncStatus,
    TableRecord,
)


def _now() -> datetime:
    return datetime.now(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_many(self, companies: list[Company]) -> int:
        """Insert-or-ignore companies by ticker. Returns number of rows."""
        count = 0
        for c in companies:
            existing = await self.session.execute(
                select(Company).where(Company.ticker == c.ticker)
            )
            if existing.scalar_one_or_none() is None:
                self.session.add(c)
                count += 1
        await self.session.flush()
        return count

    async def get_by_ticker(self, ticker: str) -> Company | None:
        res = await self.session.execute(
            select(Company).where(Company.ticker == ticker.upper())
        )
        return res.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Company | None:
        res = await self.session.execute(
            select(Company).where(
                func.lower(Company.name).contains(name.lower())
            )
        )
        return res.scalars().first()

    async def list_all(self, sector: str | None = None) -> list[Company]:
        stmt = select(Company)
        if sector:
            stmt = stmt.where(Company.sector == sector)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get(self, company_id: str) -> Company | None:
        res = await self.session.execute(select(Company).where(Company.id == company_id))
        return res.scalar_one_or_none()


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, code: str, name: str, authority_level: AuthorityLevel,
                     base_url: str = "", is_primary: bool = True) -> Source:
        res = await self.session.execute(select(Source).where(Source.code == code))
        src = res.scalar_one_or_none()
        if src is None:
            src = Source(
                code=code,
                name=name,
                authority_level=authority_level,
                base_url=base_url,
                is_primary=is_primary,
            )
            self.session.add(src)
        else:
            src.name = name
            src.authority_level = authority_level
            src.base_url = base_url or src.base_url
        await self.session.flush()
        return src

    async def get_by_code(self, code: str) -> Source | None:
        res = await self.session.execute(select(Source).where(Source.code == code))
        return res.scalar_one_or_none()

    async def list_all(self) -> list[Source]:
        res = await self.session.execute(select(Source))
        return list(res.scalars().all())


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_external(
        self, source_id: str, external_id: str
    ) -> Document | None:
        res = await self.session.execute(
            select(Document).where(
                Document.source_id == source_id,
                Document.external_id == external_id,
            )
        )
        return res.scalar_one_or_none()

    async def find_by_url(self, source_id: str, url: str) -> Document | None:
        res = await self.session.execute(
            select(Document).where(
                Document.source_id == source_id,
                Document.source_url == url,
            )
        )
        return res.scalar_one_or_none()

    async def create(
        self,
        source_id: str,
        document_type: DocumentType,
        title: str,
        source_url: str,
        external_id: str,
        content_hash: str,
        authority_level: AuthorityLevel,
        company_id: str | None = None,
        published_at: datetime | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        effective_date: datetime | None = None,
    ) -> Document:
        doc = Document(
            source_id=source_id,
            company_id=company_id,
            document_type=document_type,
            title=title,
            source_url=source_url,
            external_id=external_id,
            published_at=published_at,
            period_start=period_start,
            period_end=period_end,
            effective_date=effective_date,
            authority_level=authority_level,
            content_hash=content_hash,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get(self, document_id: str) -> Document | None:
        res = await self.session.execute(
            select(Document)
            .options(selectinload(Document.versions))
            .where(Document.id == document_id)
        )
        return res.scalar_one_or_none()

    async def get_with_source(self, document_id: str) -> Document | None:
        res = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = res.scalar_one_or_none()
        if doc is not None:
            await self.session.refresh(doc, attribute_names=["source", "company"])
        return doc

    async def update_hash(self, doc: Document, content_hash: str) -> Document:
        doc.content_hash = content_hash
        await self.session.flush()
        return doc

    async def list_documents(
        self,
        source_code: str | None = None,
        company_id: str | None = None,
        document_type: DocumentType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        stmt = select(Document).options(selectinload(Document.source))
        if source_code:
            sub = select(Source.id).where(Source.code == source_code)
            stmt = stmt.where(Document.source_id.in_(sub))
        if company_id:
            stmt = stmt.where(Document.company_id == company_id)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        stmt = stmt.order_by(Document.published_at.desc().nullslast()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class DocumentVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: str,
        content_hash: str,
        version_number: int,
        raw_path: str,
        status: ProcessingStatus = ProcessingStatus.PENDING,
    ) -> DocumentVersion:
        ver = DocumentVersion(
            document_id=document_id,
            content_hash=content_hash,
            version_number=version_number,
            raw_path=raw_path,
            processing_status=status,
        )
        self.session.add(ver)
        await self.session.flush()
        return ver

    async def get(self, version_id: str) -> DocumentVersion | None:
        res = await self.session.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id)
        )
        return res.scalar_one_or_none()

    async def latest(self, document_id: str) -> DocumentVersion | None:
        res = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_versions(self, document_id: str) -> list[DocumentVersion]:
        res = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        return list(res.scalars().all())

    async def set_status(
        self,
        version_id: str,
        status: ProcessingStatus,
        error: str = "",
    ) -> None:
        await self.session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.id == version_id)
            .values(processing_status=status)
        )
        await self.session.flush()


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, chunks: list[DocumentChunk]) -> None:
        if chunks:
            self.session.add_all(chunks)
            await self.session.flush()

    async def delete_for_version(self, version_id: str) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.version_id == version_id)
        )
        await self.session.flush()

    async def get_by_ids(self, chunk_ids: list[str]) -> list[DocumentChunk]:
        if not chunk_ids:
            return []
        stmt = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get(self, chunk_id: str) -> DocumentChunk | None:
        res = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        )
        return res.scalar_one_or_none()

    async def vector_search(
        self,
        query_embedding: list[float],
        limit: int = 20,
        company_id: str | None = None,
        document_type: DocumentType | None = None,
        source_code: str | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        min_authority: AuthorityLevel | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Cosine similarity vector search joining to latest document metadata."""
        synthetic = None
        if query_embedding:
            synthetic = "[" + ",".join(str(x) for x in query_embedding) + "]"

        where = ["dc.embedding IS NOT NULL"]
        params: dict[str, Any] = {}
        if company_id:
            params["company_id"] = company_id
            where.append("d.company_id = :company_id")
        if document_type:
            params["doc_type"] = document_type.value
            where.append("d.document_type = :doc_type")
        if source_code:
            params["source_code"] = source_code
            where.append("s.code = :source_code")
        if before:
            params["before"] = before
            where.append("d.published_at < :before")
        if after:
            params["after"] = after
            where.append("d.published_at > :after")
        if min_authority:
            params["min_auth"] = min_authority.value
            where.append(
                "d.authority_level IN "
                "('PRIMARY_REGULATOR','PRIMARY_EXCHANGE','COMPANY_PRIMARY')"
            )

        # Use the latest version per document so we never mix versions.
        sql = f"""
        WITH latest_version AS (
            SELECT DISTINCT ON (dv.document_id)
                   dv.id AS version_id, dv.document_id
            FROM document_versions dv
            ORDER BY dv.document_id, dv.version_number DESC
        )
        SELECT dc.id AS chunk_id, dc.text AS text,
               s.code AS source_code, s.name AS source_name,
               s.authority_level AS authority,
               d.title AS title, d.published_at AS published_at,
               dc.section AS section, dc.page AS page,
               dc.version_id AS version_id, d.id AS document_id,
               d.source_url AS source_url,
               1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM document_chunks dc
        JOIN latest_version lv ON lv.version_id = dc.version_id
        JOIN documents d ON d.id = lv.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {' AND '.join(where)}
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
        LIMIT :limit
        """
        params["query_vec"] = synthetic
        params["limit"] = limit

        res = await self.session.execute(text(sql).bindparams(**params))
        rows = res.mappings().all()
        chunks: list[tuple[DocumentChunk, float]] = []
        for row in rows:
            chunk = DocumentChunk(
                id=row["chunk_id"],
                text=row["text"],
                version_id=row["version_id"],
                section=row["section"],
                page=row["page"],
            )
            chunk._retrieval = {
                "document_id": row["document_id"],
                "source_code": row["source_code"],
                "source_name": row["source_name"],
                "authority_level": row["authority"],
                "title": row["title"],
                "published_at": row["published_at"],
                "source_url": row["source_url"],
            }
            chunks.append((chunk, float(row["similarity"])))
        return chunks

    async def lexical_search(
        self,
        query: str,
        limit: int = 20,
        company_id: str | None = None,
        document_type: DocumentType | None = None,
        source_code: str | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        min_authority: AuthorityLevel | None = None,
        required_term: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """PostgreSQL full-text search over the latest version of each document.

        Returns (chunk, ts_rank) tuples with the same ``_retrieval`` metadata as
        vector search so fusion can treat the two uniformly.
        """
        where = ["dc.embedding IS NOT NULL"]
        params: dict[str, Any] = {}
        if company_id:
            params["company_id"] = company_id
            where.append("d.company_id = :company_id")
        if document_type:
            params["doc_type"] = document_type.value
            where.append("d.document_type = :doc_type")
        if source_code:
            params["source_code"] = source_code
            where.append("s.code = :source_code")
        if before:
            params["before"] = before
            where.append("d.published_at < :before")
        if after:
            params["after"] = after
            where.append("d.published_at > :after")
        if min_authority:
            params["min_auth"] = min_authority.value
            where.append(
                "d.authority_level IN "
                "('PRIMARY_REGULATOR','PRIMARY_EXCHANGE','COMPANY_PRIMARY')"
            )

        # Build a sanitised tsquery from the query text + any required term.
        tsquery = self._build_tsquery(query, required_term)
        params["tsq"] = tsquery
        params["limit"] = limit

        sql = f"""
        WITH latest_version AS (
            SELECT DISTINCT ON (dv.document_id)
                   dv.id AS version_id, dv.document_id
            FROM document_versions dv
            ORDER BY dv.document_id, dv.version_number DESC
        )
        SELECT dc.id AS chunk_id, dc.text AS text,
               s.code AS source_code, s.name AS source_name,
               s.authority_level AS authority,
               d.title AS title, d.published_at AS published_at,
               dc.section AS section, dc.page AS page,
               dc.version_id AS version_id, d.id AS document_id,
               d.source_url AS source_url,
               ts_rank(to_tsvector('english', dc.text), to_tsquery('english', :tsq))
                   AS score,
               ts_headline('english', dc.text, to_tsquery('english', :tsq),
                           'StartSel=<mark>, StopSel=</mark>, MaxFragments=2')
                   AS highlight
        FROM document_chunks dc
        JOIN latest_version lv ON lv.version_id = dc.version_id
        JOIN documents d ON d.id = lv.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {' AND '.join(where)}
          AND to_tsvector('english', dc.text) @@ to_tsquery('english', :tsq)
        ORDER BY score DESC
        LIMIT :limit
        """
        res = await self.session.execute(text(sql).bindparams(**params))
        rows = res.mappings().all()
        chunks: list[tuple[DocumentChunk, float]] = []
        for row in rows:
            chunk = DocumentChunk(
                id=row["chunk_id"],
                text=row["text"],
                version_id=row["version_id"],
                section=row["section"],
                page=row["page"],
            )
            chunk._retrieval = {
                "document_id": row["document_id"],
                "source_code": row["source_code"],
                "source_name": row["source_name"],
                "authority_level": row["authority"],
                "title": row["title"],
                "published_at": row["published_at"],
                "source_url": row["source_url"],
                "highlight": row.get("highlight", ""),
            }
            chunks.append((chunk, float(row["score"])))
        return chunks

    def _build_tsquery(self, query: str, required: str | None = None) -> str:
        import re

        tokens = re.findall(r"[a-z0-9]+", (query + " " + (required or "")).lower())
        # Keep the most discriminative terms, drop stopwords-ish short terms.
        terms = [t for t in tokens if len(t) > 2][:6]
        if not terms:
            terms = tokens[:6]
        if not terms:
            return "'ng'"
        return " & ".join(f"'{t}'" for t in terms)


class TableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, tables: list[TableRecord]) -> None:
        if tables:
            self.session.add_all(tables)
            await self.session.flush()

    async def search_by_text(self, query: str, limit: int = 20) -> list[TableRecord]:
        ts_query = " & ".join(f"'{w}'" for w in query.split()[:8])
        sql = text(
            "SELECT * FROM tables "
            "WHERE to_tsvector('english', normalized_text || ' ' || title) "
            "   @@ to_tsquery('english', :q) "
            "ORDER BY ts_rank(to_tsvector('english', normalized_text || ' ' || title), "
            "              to_tsquery('english', :q)) DESC LIMIT :limit"
        )
        res = await self.session.execute(sql, {"q": ts_query, "limit": limit})
        return [self._from_row(r) for r in res.mappings().all()]

    def _from_row(self, row: Any) -> TableRecord:
        tbl = TableRecord(
            id=row["id"],
            document_id=row["document_id"],
            version_id=row["version_id"],
            page=row["page"],
            section=row["section"],
            title=row["title"],
            headers=row["headers"],
            rows=row["rows"],
            normalized_text=row["normalized_text"],
            currency=row["currency"],
            units=row["units"],
        )
        return tbl


class FinancialMetricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, metrics: list[FinancialMetric]) -> None:
        if metrics:
            self.session.add_all(metrics)
            await self.session.flush()

    async def get_series(
        self, company_id: str, metric: str
    ) -> list[FinancialMetric]:
        res = await self.session.execute(
            select(FinancialMetric)
            .where(
                FinancialMetric.company_id == company_id,
                FinancialMetric.metric == metric,
            )
            .order_by(FinancialMetric.period_end.asc())
        )
        return list(res.scalars().all())


class SyncRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(self, source_code: str) -> SyncRun:
        run = SyncRun(source_code=source_code, status=SyncStatus.RUNNING)
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish(
        self,
        run: SyncRun,
        status: SyncStatus,
        discovered: int = 0,
        added: int = 0,
        updated: int = 0,
        failed: int = 0,
        error: str = "",
    ) -> SyncRun:
        run.status = status
        run.finished_at = _now()
        run.last_checked_at = _now()
        run.documents_discovered = discovered
        run.documents_added = added
        run.documents_updated = updated
        run.documents_failed = failed
        run.error = error
        await self.session.flush()
        return run

    async def latest(self, source_code: str) -> SyncRun | None:
        res = await self.session.execute(
            select(SyncRun)
            .where(SyncRun.source_code == source_code)
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_runs(self, source_code: str | None = None) -> list[SyncRun]:
        stmt = select(SyncRun).order_by(SyncRun.started_at.desc()).limit(50)
        if source_code:
            stmt = stmt.where(SyncRun.source_code == source_code)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class CitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: str,
        chunk_id: str | None = None,
        version_id: str | None = None,
        section: str = "",
        page: int | None = None,
        source_url: str = "",
        published_at: datetime | None = None,
        snippet: str = "",
    ) -> Citation:
        citation = Citation(
            document_id=document_id,
            chunk_id=chunk_id,
            version_id=version_id,
            section=section,
            page=page,
            source_url=source_url,
            published_at=published_at,
            snippet=snippet,
        )
        self.session.add(citation)
        await self.session.flush()
        return citation

    async def get(self, citation_id: str) -> Citation | None:
        res = await self.session.execute(
            select(Citation).where(Citation.id == citation_id)
        )
        return res.scalar_one_or_none()


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: str,
        version_id: str,
        stage: str,
        status: ProcessingStatus = ProcessingStatus.PENDING,
    ) -> IngestionJob:
        job = IngestionJob(
            document_id=document_id,
            version_id=version_id,
            stage=stage,
            status=status,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def fail(self, job: IngestionJob, error: str) -> IngestionJob:
        job.status = ProcessingStatus.FAILED
        job.error = error
        job.retry_count += 1
        await self.session.flush()
        return job

    async def complete(self, job: IngestionJob) -> IngestionJob:
        job.status = ProcessingStatus.COMPLETED
        await self.session.flush()
        return job

    async def list_documents_pending(self, stage: str, limit: int = 50) -> list[DocumentVersion]:
        res = await self.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.processing_status == ProcessingStatus.PENDING)
            .order_by(DocumentVersion.retrieved_at.asc())
            .limit(limit)
        )
        return list(res.scalars().all())
