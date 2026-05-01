"""SQLAlchemy models for chapter-progressive analysis."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from novel_analyzer.database.base import Base, TimestampSoftDeleteMixin


class NovelSource(TimestampSoftDeleteMixin, Base):
    __tablename__ = "novel_sources"

    title: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(Text())
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    manifests: Mapped[list[ChapterManifest]] = relationship(back_populates="novel")
    runs: Mapped[list[AnalysisRun]] = relationship(back_populates="novel")


class ChapterManifest(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_manifests"
    __table_args__ = (UniqueConstraint("novel_id", "version", name="uq_manifest_version"),)

    novel_id: Mapped[str] = mapped_column(ForeignKey("novel_sources.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    splitter_version: Mapped[str] = mapped_column(String(64))
    chapter_count: Mapped[int] = mapped_column(Integer)
    notes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    novel: Mapped[NovelSource] = relationship(back_populates="manifests")
    segments: Mapped[list[ChapterSegment]] = relationship(back_populates="manifest")
    runs: Mapped[list[AnalysisRun]] = relationship(back_populates="manifest")


class ChapterSegment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_segments"
    __table_args__ = (UniqueConstraint("manifest_id", "chapter_index", name="uq_manifest_chapter"),)

    manifest_id: Mapped[str] = mapped_column(ForeignKey("chapter_manifests.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    raw_heading: Mapped[str] = mapped_column(Text())
    normalized_chapter_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_title: Mapped[str] = mapped_column(Text())
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))

    manifest: Mapped[ChapterManifest] = relationship(back_populates="segments")


class AnalysisRun(TimestampSoftDeleteMixin, Base):
    __tablename__ = "analysis_runs"

    novel_id: Mapped[str] = mapped_column(ForeignKey("novel_sources.id"), index=True)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("chapter_manifests.id"), index=True)
    llm_base_url: Mapped[str] = mapped_column(Text())
    llm_model_name: Mapped[str] = mapped_column(String(128))
    analysis_profile: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    active_branch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    novel: Mapped[NovelSource] = relationship(back_populates="runs")
    manifest: Mapped[ChapterManifest] = relationship(back_populates="runs")
    branches: Mapped[list[RunBranch]] = relationship(back_populates="run")
    raw_outputs: Mapped[list[ChapterRawOutput]] = relationship(back_populates="run")


class RunBranch(TimestampSoftDeleteMixin, Base):
    __tablename__ = "run_branches"

    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("run_branches.id"),
        nullable=True,
    )
    fork_after_chapter_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="active")

    run: Mapped[AnalysisRun] = relationship(back_populates="branches", foreign_keys=[run_id])
    checkpoints: Mapped[list[RunCheckpoint]] = relationship(back_populates="branch")
    artifacts: Mapped[list[ChapterArtifact]] = relationship(back_populates="branch")
    jobs: Mapped[list[ChapterJob]] = relationship(back_populates="branch")
    raw_outputs: Mapped[list[ChapterRawOutput]] = relationship(back_populates="branch")
    retrieval_documents: Mapped[list[RetrievalDocument]] = relationship(back_populates="branch")
    facts: Mapped[list[FactRecord]] = relationship(back_populates="branch")
    windows: Mapped[list[WindowArtifact]] = relationship(back_populates="branch")
    graph_nodes: Mapped[list[GraphNode]] = relationship(back_populates="branch")
    graph_edges: Mapped[list[GraphEdge]] = relationship(back_populates="branch")
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(back_populates="branch")


class RunCheckpoint(TimestampSoftDeleteMixin, Base):
    __tablename__ = "run_checkpoints"
    __table_args__ = (UniqueConstraint("branch_id", "chapter_index", name="uq_branch_checkpoint"),)

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    langgraph_checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    inherited_from_branch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_inherited: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(32), default="active")

    branch: Mapped[RunBranch] = relationship(back_populates="checkpoints")


class ChapterArtifact(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_artifacts"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    artifact_type: Mapped[str] = mapped_column(String(64), default="chapter_analysis")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="validated")
    visibility: Mapped[str] = mapped_column(String(32), default="active")
    source_kind: Mapped[str] = mapped_column(String(32), default="model")
    participates_in_downstream: Mapped[bool] = mapped_column(Boolean, default=True)
    inherited_from_branch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_inherited: Mapped[bool] = mapped_column(Boolean, default=False)

    branch: Mapped[RunBranch] = relationship(back_populates="artifacts")


class ChapterJob(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_jobs"
    __table_args__ = (UniqueConstraint("branch_id", "chapter_index", name="uq_branch_job"),)

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heartbeat_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    queue_name: Mapped[str] = mapped_column(String(64), default="default")
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    control_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped[RunBranch] = relationship(back_populates="jobs")


class ChapterJobEvent(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_job_events"

    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer, index=True)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapter_jobs.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text())
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class PipelineRun(TimestampSoftDeleteMixin, Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="range")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    target_from_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_to_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    provider_profile: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    branch: Mapped[RunBranch] = relationship(back_populates="pipeline_runs")


class ChapterRawOutput(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_raw_outputs"

    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    job_attempt: Mapped[int] = mapped_column(Integer, default=1)
    prompt_version: Mapped[str] = mapped_column(String(64), default="chapter_analysis_v0_2")
    schema_version: Mapped[str] = mapped_column(String(64), default="chapter_analysis_v0_2")
    raw_response_text: Mapped[str] = mapped_column(Text())
    parsed_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="parsed")
    parse_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    invocation_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    run: Mapped[AnalysisRun] = relationship(back_populates="raw_outputs")
    branch: Mapped[RunBranch] = relationship(back_populates="raw_outputs")


class RetrievalDocument(TimestampSoftDeleteMixin, Base):
    __tablename__ = "retrieval_documents"
    __table_args__ = (UniqueConstraint("branch_id", "chapter_index", name="uq_retrieval_document"),)

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text())
    summary_text: Mapped[str] = mapped_column(Text())
    bm25_text: Mapped[str] = mapped_column(Text())
    keyword_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    query_hints: Mapped[list[str]] = mapped_column(JSON, default=list)
    materialization_status: Mapped[str] = mapped_column(String(32), default="ready")

    branch: Mapped[RunBranch] = relationship(back_populates="retrieval_documents")
    chunks: Mapped[list[RetrievalChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class RetrievalChunk(TimestampSoftDeleteMixin, Base):
    __tablename__ = "retrieval_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_order", name="uq_document_chunk_order"),
    )

    document_id: Mapped[str] = mapped_column(ForeignKey("retrieval_documents.id"), index=True)
    chunk_order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text())
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    embedding_status: Mapped[str] = mapped_column(String(32), default="pending")
    keyword_list: Mapped[list[str]] = mapped_column(JSON, default=list)

    document: Mapped[RetrievalDocument] = relationship(back_populates="chunks")
    embedding: Mapped[ChunkEmbedding | None] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ChunkEmbedding(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", name="uq_chunk_embedding_chunk"),)

    chunk_id: Mapped[str] = mapped_column(ForeignKey("retrieval_chunks.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    vector_dim: Mapped[int] = mapped_column(Integer)
    vector_payload: Mapped[list[float]] = mapped_column(JSON, default=list)
    l2_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    chunk: Mapped[RetrievalChunk] = relationship(back_populates="embedding")


class FactRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "fact_records"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    fact_type: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(Text())
    evidence_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    branch: Mapped[RunBranch] = relationship(back_populates="facts")


class WindowArtifact(TimestampSoftDeleteMixin, Base):
    __tablename__ = "window_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "window_start_chapter",
            "window_end_chapter",
            name="uq_window_artifact_range",
        ),
    )

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    window_start_chapter: Mapped[int] = mapped_column(Integer)
    window_end_chapter: Mapped[int] = mapped_column(Integer)
    window_type: Mapped[str] = mapped_column(String(32), default="fixed_5")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ready")

    branch: Mapped[RunBranch] = relationship(back_populates="windows")


class GraphNode(TimestampSoftDeleteMixin, Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint("branch_id", "node_type", "label", name="uq_graph_node_identity"),
    )

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    node_type: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(Text())
    chapter_first_seen: Mapped[int] = mapped_column(Integer)
    chapter_last_seen: Mapped[int] = mapped_column(Integer)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    branch: Mapped[RunBranch] = relationship(back_populates="graph_nodes")
    outgoing_edges: Mapped[list[GraphEdge]] = relationship(
        back_populates="source_node",
        foreign_keys="GraphEdge.source_node_id",
    )
    incoming_edges: Mapped[list[GraphEdge]] = relationship(
        back_populates="target_node",
        foreign_keys="GraphEdge.target_node_id",
    )


class GraphEdge(TimestampSoftDeleteMixin, Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_graph_edge_identity",
        ),
    )

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    edge_type: Mapped[str] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    chapter_first_seen: Mapped[int] = mapped_column(Integer)
    chapter_last_seen: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    branch: Mapped[RunBranch] = relationship(back_populates="graph_edges")
    source_node: Mapped[GraphNode] = relationship(
        back_populates="outgoing_edges",
        foreign_keys=[source_node_id],
    )
    target_node: Mapped[GraphNode] = relationship(
        back_populates="incoming_edges",
        foreign_keys=[target_node_id],
    )


class GateCheckerResultRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "gate_checker_results"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer, index=True)
    checker_name: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    visibility: Mapped[str] = mapped_column(String(32), default="active")


class ChapterRiskCardRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "chapter_risk_cards"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer, index=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    visibility: Mapped[str] = mapped_column(String(32), default="active")


class ClusterReviewRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "cluster_review_records"
    __table_args__ = (
        UniqueConstraint("branch_id", "cluster_key", name="uq_cluster_review_branch_key"),
    )

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    cluster_key: Mapped[str] = mapped_column(String(255), index=True)
    cluster_status: Mapped[str] = mapped_column(String(32), default="open")
    review_result: Mapped[str] = mapped_column(String(64), default="")
    review_notes: Mapped[str] = mapped_column(Text(), default="")
    review_owner: Mapped[str] = mapped_column(String(255), default="")
    review_actor: Mapped[str] = mapped_column(String(255), default="")
    resolved_at_text: Mapped[str] = mapped_column(String(64), default="")
    visibility: Mapped[str] = mapped_column(String(32), default="active")


class ClusterReviewEventRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "cluster_review_event_records"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    cluster_key: Mapped[str] = mapped_column(String(255), index=True)
    previous_cluster_status: Mapped[str] = mapped_column(String(32), default="")
    previous_review_result: Mapped[str] = mapped_column(String(64), default="")
    previous_review_notes: Mapped[str] = mapped_column(Text(), default="")
    previous_review_owner: Mapped[str] = mapped_column(String(255), default="")
    previous_review_actor: Mapped[str] = mapped_column(String(255), default="")
    previous_resolved_at_text: Mapped[str] = mapped_column(String(64), default="")
    cluster_status: Mapped[str] = mapped_column(String(32), default="open")
    review_result: Mapped[str] = mapped_column(String(64), default="")
    review_notes: Mapped[str] = mapped_column(Text(), default="")
    review_owner: Mapped[str] = mapped_column(String(255), default="")
    review_actor: Mapped[str] = mapped_column(String(255), default="")
    resolved_at_text: Mapped[str] = mapped_column(String(64), default="")
    event_type: Mapped[str] = mapped_column(String(64), default="status_update")


class RiskSemanticSignalRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "risk_semantic_signals"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer, index=True)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    source_field: Mapped[str] = mapped_column(String(128), default="")
    raw_text: Mapped[str] = mapped_column(Text())
    canonical_label: Mapped[str] = mapped_column(Text(), default="")
    canonical_group: Mapped[str] = mapped_column(String(255), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    vector_payload: Mapped[list[float]] = mapped_column(JSON, default=list)
    vector_text: Mapped[str] = mapped_column(Text(), default="")
    vector_dim: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ready")


class RiskSignalLinkRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "risk_signal_links"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer, index=True, default=0)
    from_signal_id: Mapped[str] = mapped_column(ForeignKey("risk_semantic_signals.id"), index=True)
    to_signal_id: Mapped[str] = mapped_column(ForeignKey("risk_semantic_signals.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class RiskSignalClusterRecord(TimestampSoftDeleteMixin, Base):
    __tablename__ = "risk_signal_clusters"

    branch_id: Mapped[str] = mapped_column(ForeignKey("run_branches.id"), index=True)
    cluster_key: Mapped[str] = mapped_column(String(255), index=True)
    signal_type: Mapped[str] = mapped_column(String(64), index=True)
    summary_text: Mapped[str] = mapped_column(Text(), default="")
    signal_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
