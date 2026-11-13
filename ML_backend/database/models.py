"""
models.py - SQLAlchemy 2.x Declarative ORM Models for MANET Database.
Project: Ensuring Security and Privacy in Decentralized MANETs.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SimulationRun(Base):
    """Master simulation execution record decoupling simulation vs persistence lifecycles."""
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(16), default="AODV", nullable=False)
    num_nodes: Mapped[int] = mapped_column(Integer, nullable=False)
    num_malicious: Mapped[int] = mapped_column(Integer, nullable=False)
    attack_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    packet_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    simulation_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ground_truth_malicious: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string

    # Lifecycle separation: NS-3 simulation execution vs SQLite database ingestion
    simulation_status: Mapped[str] = mapped_column(
        String(20),
        default="running",
        nullable=False,
        index=True
    )  # running | completed | failed
    persistence_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True
    )  # pending | completed | failed | retry_pending

    simulation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persistence_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    persisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships to child entities
    metrics: Mapped[List["SimulationMetric"]] = relationship(
        "SimulationMetric", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    energy_metrics: Mapped[List["NodeEnergyMetric"]] = relationship(
        "NodeEnergyMetric", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    ml_predictions: Mapped[List["MLPrediction"]] = relationship(
        "MLPrediction", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    trust_evaluations: Mapped[List["TrustEvaluation"]] = relationship(
        "TrustEvaluation", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    routing_records: Mapped[List["RoutingRecord"]] = relationship(
        "RoutingRecord", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    prevention_events: Mapped[List["PreventionEvent"]] = relationship(
        "PreventionEvent", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    ingestion_ledgers: Mapped[List["ArtifactIngestionLedger"]] = relationship(
        "ArtifactIngestionLedger", back_populates="simulation_run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["SimulationArtifact"]] = relationship(
        "SimulationArtifact", back_populates="simulation_run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "simulation_status IN ('running', 'completed', 'failed')",
            name="chk_simulation_status"
        ),
        CheckConstraint(
            "persistence_status IN ('pending', 'completed', 'failed', 'retry_pending')",
            name="chk_persistence_status"
        ),
    )


class SimulationMetric(Base):
    """Aggregate flow-level network performance metrics from FlowMonitor XML files."""
    __tablename__ = "simulation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # 'baseline' or 'attack'
    flow_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dest_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    tx_packets: Mapped[int] = mapped_column(Integer, nullable=False)
    rx_packets: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pdr: Mapped[float] = mapped_column(Float, nullable=False)
    throughput_kbps: Mapped[float] = mapped_column(Float, nullable=False)
    avg_delay_ms: Mapped[float] = mapped_column(Float, nullable=False)
    avg_jitter_ms: Mapped[float] = mapped_column(Float, nullable=False)
    packet_loss_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="metrics"
    )

    __table_args__ = (
        CheckConstraint("phase IN ('baseline', 'attack')", name="chk_sim_metric_phase"),
        UniqueConstraint("simulation_run_id", "phase", "flow_id", name="uq_simulation_metrics_flow"),
        Index("ix_simulation_metrics_run_phase", "simulation_run_id", "phase"),
    )


class NodeEnergyMetric(Base):
    """Per-node residual energy and consumption parsed from energy CSV files."""
    __tablename__ = "node_energy_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # 'baseline' or 'attack'
    node_id: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_energy_j: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_energy_j: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_energy_j: Mapped[float] = mapped_column(Float, nullable=False)
    residual_pct: Mapped[float] = mapped_column(Float, nullable=False)

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="energy_metrics"
    )

    __table_args__ = (
        CheckConstraint("phase IN ('baseline', 'attack')", name="chk_node_energy_phase"),
        UniqueConstraint("simulation_run_id", "phase", "node_id", name="uq_node_energy_metrics"),
        Index("ix_node_energy_run_phase", "simulation_run_id", "phase"),
    )


class ModelRegistry(Base):
    """Metadata, artifact weights, and evaluation metrics for Classical ML, LSTM, and FL models."""
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)  # RandomForest, XGBoost, CatBoost, SVM, MLP, LSTM, FederatedLearning
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # classical_ml, deep_learning_trust, federated_learning
    version_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)

    # Domain metrics (nullable to accommodate Classical ML vs LSTM vs FL differences)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    f1_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fpr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    confusion_matrix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON matrix
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ml_predictions: Mapped[List["MLPrediction"]] = relationship(
        "MLPrediction", back_populates="model"
    )

    __table_args__ = (
        UniqueConstraint("model_name", "version_tag", "file_hash_sha256", name="uq_model_registry_version"),
        Index("ix_model_registry_active", "model_name", "is_active"),
    )


class MLPrediction(Base):
    """Inference predictions from Classical ML models evaluated on cross-layer feature rows."""
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_registry.id"), nullable=False, index=True
    )
    time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rx_packets: Mapped[float] = mapped_column(Float, nullable=False)
    control_freq: Mapped[float] = mapped_column(Float, nullable=False)
    ground_truth_label: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_label: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="ml_predictions"
    )
    model: Mapped["ModelRegistry"] = relationship(
        "ModelRegistry", back_populates="ml_predictions"
    )

    __table_args__ = (
        UniqueConstraint("simulation_run_id", "model_id", "time_sec", "node_id", name="uq_ml_predictions_entry"),
        Index("ix_ml_predictions_run_node", "simulation_run_id", "node_id"),
    )


class TrustEvaluation(Base):
    """Dynamic LSTM trust score and anomaly detection output per node interval."""
    __tablename__ = "trust_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    is_malicious: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 if trust_score < threshold else 0
    inferred_action: Mapped[str] = mapped_column(String(32), nullable=False)  # 'Blacklisted' if is_malicious == 1 else 'None'

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="trust_evaluations"
    )

    __table_args__ = (
        UniqueConstraint("simulation_run_id", "time_sec", "node_id", name="uq_trust_evaluations_entry"),
        Index("ix_trust_evaluations_run_time", "simulation_run_id", "time_sec"),
        Index("ix_trust_evaluations_node", "simulation_run_id", "node_id"),
    )


class RoutingRecord(Base):
    """Multi-hop route discovery trace for attack pass and mitigated pass."""
    __tablename__ = "routing_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # 'attack_pass1' or 'mitigated_pass2'
    source_node: Mapped[int] = mapped_column(Integer, nullable=False)
    dest_node: Mapped[int] = mapped_column(Integer, nullable=False)
    hop_count: Mapped[int] = mapped_column(Integer, nullable=False)
    route_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    destination_reached: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hops_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of hop dicts
    has_malicious_node: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="routing_records"
    )

    __table_args__ = (
        CheckConstraint("phase IN ('attack_pass1', 'mitigated_pass2')", name="chk_routing_phase"),
        UniqueConstraint("simulation_run_id", "phase", "source_node", "dest_node", name="uq_routing_records_entry"),
        Index("ix_routing_records_run_phase", "simulation_run_id", "phase"),
    )


class PreventionEvent(Base):
    """Chronological NS-3 mitigation actuation and runtime verification audit record."""
    __tablename__ = "prevention_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(24), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="prevention_events"
    )

    __table_args__ = (
        UniqueConstraint("simulation_run_id", "sequence", name="uq_prevention_events_run_sequence"),
        Index("ix_prevention_events_run_node", "simulation_run_id", "node_id"),
        Index("ix_prevention_events_run_time", "simulation_run_id", "time_sec"),
        CheckConstraint("action_type IN ('INTERFACE_DOWN', 'AODV_BLACKLIST', 'RESTORE')", name="chk_prevention_action"),
        CheckConstraint("execution_status IN ('SUCCESS', 'FAILED', 'DUPLICATE_IGNORED', 'UNVERIFIED')", name="chk_prevention_status"),
        CheckConstraint("trigger_source IN ('LSTM_PREDICTION', 'STATIC_EXCLUSION')", name="chk_prevention_trigger"),
    )


class ArtifactIngestionLedger(Base):
    """Append-only audit ledger recording every artifact ingestion attempt, status, and cryptographic hash."""
    __tablename__ = "artifact_ingestion_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(24), nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="ingestion_ledgers"
    )

    __table_args__ = (
        UniqueConstraint("simulation_run_id", "artifact_type", "attempt_number", name="uq_artifact_ledger_attempt"),
        Index("ix_artifact_ledger_run_art", "simulation_run_id", "artifact_type"),
        CheckConstraint(
            "ingestion_status IN ('SUCCESS', 'AUTHENTIC_EMPTY', 'FAILED', 'SKIPPED_NO_ARTIFACT', 'ALREADY_INGESTED')",
            name="chk_ledger_status",
        ),
        CheckConstraint(
            "(ingestion_status = 'SKIPPED_NO_ARTIFACT' AND file_hash_sha256 IS NULL) OR "
            "(ingestion_status != 'SKIPPED_NO_ARTIFACT' AND file_hash_sha256 IS NOT NULL)",
            name="chk_ledger_hash_nullability",
        ),
    )


class SimulationArtifact(Base):
    """Audit register of all on-disk artifacts generated per simulation run."""
    __tablename__ = "simulation_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)  # flow_xml, energy_csv, trace_csv, route_tr, routing_json, lstm_pred_csv, classical_ml_csv
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    simulation_run: Mapped["SimulationRun"] = relationship(
        "SimulationRun", back_populates="artifacts"
    )

    __table_args__ = (
        UniqueConstraint("simulation_run_id", "file_type", name="uq_simulation_artifacts_entry"),
    )

