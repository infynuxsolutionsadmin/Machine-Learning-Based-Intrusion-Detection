"""
c4a1e9b23f81_create_prevention_events_v2_and_ledger.py

Revision ID: c4a1e9b23f81
Revises: 514de1c2fb47
Create Date: 2026-11-12 14:30:00.000000

Phase: C4 - Additive SQLite Migration for Prevention Event Logging V2 & Ingestion Ledger.
Implements Universal Downgrade Preflight protecting authentic simulation records.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a1e9b23f81'
down_revision: Union[str, None] = '514de1c2fb47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Handle prevention_events table
    if "prevention_events" in tables:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM prevention_events")).scalar() or 0
        if count > 0:
            # Rename populated legacy table to preserve history
            op.rename_table("prevention_events", "prevention_events_legacy")
        else:
            # Drop empty legacy table
            with op.batch_alter_table("prevention_events", schema=None) as batch_op:
                try:
                    batch_op.drop_index("ix_prevention_events_run_match")
                except Exception:
                    pass
                try:
                    batch_op.drop_index("ix_prevention_events_run_node")
                except Exception:
                    pass
                try:
                    batch_op.drop_index(batch_op.f("ix_prevention_events_simulation_run_id"))
                except Exception:
                    pass
            op.drop_table("prevention_events")

    # 2. Create target prevention_events table (V2 schema)
    op.create_table(
        "prevention_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulation_run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_sec", sa.Float(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("execution_status", sa.String(length=20), nullable=False),
        sa.Column("trigger_source", sa.String(length=24), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("action_type IN ('INTERFACE_DOWN', 'AODV_BLACKLIST', 'RESTORE')", name="chk_prevention_action"),
        sa.CheckConstraint("execution_status IN ('SUCCESS', 'FAILED', 'DUPLICATE_IGNORED', 'UNVERIFIED')", name="chk_prevention_status"),
        sa.CheckConstraint("trigger_source IN ('LSTM_PREDICTION', 'STATIC_EXCLUSION')", name="chk_prevention_trigger"),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_run_id", "sequence", name="uq_prevention_events_run_sequence"),
    )
    with op.batch_alter_table("prevention_events", schema=None) as batch_op:
        batch_op.create_index("ix_prevention_events_run_node", ["simulation_run_id", "node_id"], unique=False)
        batch_op.create_index("ix_prevention_events_run_time", ["simulation_run_id", "time_sec"], unique=False)
        batch_op.create_index(batch_op.f("ix_prevention_events_simulation_run_id"), ["simulation_run_id"], unique=False)

    # 3. Create artifact_ingestion_ledger table
    op.create_table(
        "artifact_ingestion_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulation_run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("ingestion_status", sa.String(length=24), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("ingestion_status IN ('SUCCESS', 'AUTHENTIC_EMPTY', 'FAILED', 'SKIPPED_NO_ARTIFACT', 'ALREADY_INGESTED')", name="chk_ledger_status"),
        sa.CheckConstraint("(ingestion_status = 'SKIPPED_NO_ARTIFACT' AND file_hash_sha256 IS NULL) OR (ingestion_status != 'SKIPPED_NO_ARTIFACT' AND file_hash_sha256 IS NOT NULL)", name="chk_ledger_hash_nullability"),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_run_id", "artifact_type", "attempt_number", name="uq_artifact_ledger_attempt"),
    )
    with op.batch_alter_table("artifact_ingestion_ledger", schema=None) as batch_op:
        batch_op.create_index("ix_artifact_ledger_run_art", ["simulation_run_id", "artifact_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_artifact_ingestion_ledger_simulation_run_id"), ["simulation_run_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Universal Downgrade Preflight: If new table has rows -> STRICT ABORT
    if "prevention_events" in tables:
        count = conn.execute(sa.text("SELECT COUNT(*) FROM prevention_events")).scalar() or 0
        if count > 0:
            raise RuntimeError(
                f"STRICT ABORT: Table 'prevention_events' contains {count} authentic event rows. "
                "Automatic downgrade would permanently destroy simulation evidence. "
                "Manual export required before downgrade."
            )
        with op.batch_alter_table("prevention_events", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_prevention_events_simulation_run_id"))
            batch_op.drop_index("ix_prevention_events_run_time")
            batch_op.drop_index("ix_prevention_events_run_node")
        op.drop_table("prevention_events")

    if "artifact_ingestion_ledger" in tables:
        with op.batch_alter_table("artifact_ingestion_ledger", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_artifact_ingestion_ledger_simulation_run_id"))
            batch_op.drop_index("ix_artifact_ledger_run_art")
        op.drop_table("artifact_ingestion_ledger")

    # Restore legacy table if it was renamed, or recreate empty legacy table
    if "prevention_events_legacy" in tables:
        op.rename_table("prevention_events_legacy", "prevention_events")
    else:
        op.create_table(
            "prevention_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("simulation_run_id", sa.Integer(), nullable=False),
            sa.Column("node_id", sa.Integer(), nullable=False),
            sa.Column("is_ground_truth_malicious", sa.Boolean(), nullable=False),
            sa.Column("is_detected_by_lstm", sa.Boolean(), nullable=False),
            sa.Column("is_blacklisted_in_ns3", sa.Boolean(), nullable=False),
            sa.Column("match_category", sa.String(length=24), nullable=False),
            sa.Column("route_recovered", sa.Boolean(), nullable=False),
            sa.Column("event_timestamp", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("prevention_events", schema=None) as batch_op:
            batch_op.create_index("ix_prevention_events_run_match", ["simulation_run_id", "match_category"], unique=False)
            batch_op.create_index("ix_prevention_events_run_node", ["simulation_run_id", "node_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_prevention_events_simulation_run_id"), ["simulation_run_id"], unique=False)

