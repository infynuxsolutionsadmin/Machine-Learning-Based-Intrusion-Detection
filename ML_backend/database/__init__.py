"""
database package - SQLAlchemy SQLite persistence layer for MANET Backend.
"""
from .base import Base
from .models import (
    ArtifactIngestionLedger,
    MLPrediction,
    ModelRegistry,
    NodeEnergyMetric,
    PreventionEvent,
    RoutingRecord,
    SimulationArtifact,
    SimulationMetric,
    SimulationRun,
    TrustEvaluation,
)
from .session import (
    DEFAULT_DB_PATH,
    SessionLocal,
    create_db_engine,
    db_write_lock,
    engine,
    get_db,
    get_sqlite_url,
    get_write_session,
    init_db,
    safe_wal_checkpoint,
)

from .ingestion_service import (
    compute_file_sha256,
    extract_run_metadata,
    get_simulation_artifact_catalog,
    ingest_classical_ml_predictions,
    ingest_model_registry,
    ingest_prevention_events,
    ingest_routing_records,
    ingest_simulation_core,
    ingest_trust_evaluations,
    parse_artifact_records,
    parse_energy_metrics,
    parse_flow_metrics,
    resolve_run_started_at,
)

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "get_write_session",
    "init_db",
    "safe_wal_checkpoint",
    "create_db_engine",
    "get_sqlite_url",
    "DEFAULT_DB_PATH",
    "db_write_lock",
    "SimulationRun",
    "SimulationMetric",
    "NodeEnergyMetric",
    "ModelRegistry",
    "MLPrediction",
    "TrustEvaluation",
    "RoutingRecord",
    "PreventionEvent",
    "ArtifactIngestionLedger",
    "SimulationArtifact",
    "extract_run_metadata",
    "parse_flow_metrics",
    "parse_energy_metrics",
    "parse_artifact_records",
    "get_simulation_artifact_catalog",
    "compute_file_sha256",
    "ingest_simulation_core",
    "ingest_model_registry",
    "ingest_classical_ml_predictions",
    "ingest_trust_evaluations",
    "ingest_routing_records",
    "ingest_prevention_events",
    "resolve_run_started_at",
]


