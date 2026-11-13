"""
f7a2d3e4b5c6_drop_unused_federated_learning_tables.py

Revision ID: f7a2d3e4b5c6
Revises: c4a1e9b23f81
Create Date: 2026-11-12 23:40:00.000000

Objective: Clean removal of verified empty, unused Federated Learning tables:
1. federated_learning_clients
2. federated_learning_rounds
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a2d3e4b5c6'
down_revision: Union[str, None] = 'c4a1e9b23f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Safety Preflight: verify row counts before dropping
    if 'federated_learning_clients' in tables:
        count_c = conn.execute(sa.text("SELECT COUNT(*) FROM federated_learning_clients")).scalar() or 0
        if count_c > 0:
            raise RuntimeError(f"ABORT MIGRATION: federated_learning_clients contains {count_c} records!")

    if 'federated_learning_rounds' in tables:
        count_r = conn.execute(sa.text("SELECT COUNT(*) FROM federated_learning_rounds")).scalar() or 0
        if count_r > 0:
            raise RuntimeError(f"ABORT MIGRATION: federated_learning_rounds contains {count_r} records!")

    # 1. Drop child table: federated_learning_clients
    if 'federated_learning_clients' in tables:
        indexes_c = [idx['name'] for idx in inspector.get_indexes('federated_learning_clients')]
        with op.batch_alter_table('federated_learning_clients', schema=None) as batch_op:
            if 'ix_fl_clients_round_client' in indexes_c:
                batch_op.drop_index('ix_fl_clients_round_client')
            if 'ix_federated_learning_clients_round_id' in indexes_c:
                batch_op.drop_index('ix_federated_learning_clients_round_id')
        op.drop_table('federated_learning_clients')

    # 2. Drop parent table: federated_learning_rounds
    if 'federated_learning_rounds' in tables:
        indexes_r = [idx['name'] for idx in inspector.get_indexes('federated_learning_rounds')]
        with op.batch_alter_table('federated_learning_rounds', schema=None) as batch_op:
            if 'ix_fl_rounds_round_num' in indexes_r:
                batch_op.drop_index('ix_fl_rounds_round_num')
            if 'ix_federated_learning_rounds_simulation_run_id' in indexes_r:
                batch_op.drop_index('ix_federated_learning_rounds_simulation_run_id')
            if 'ix_federated_learning_rounds_session_id' in indexes_r:
                batch_op.drop_index('ix_federated_learning_rounds_session_id')
        op.drop_table('federated_learning_rounds')


def downgrade() -> None:
    # 1. Re-create parent table: federated_learning_rounds
    op.create_table(
        'federated_learning_rounds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('simulation_run_id', sa.Integer(), nullable=True),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('global_loss', sa.Float(), nullable=False),
        sa.Column('global_accuracy', sa.Float(), nullable=False),
        sa.Column('participating_clients', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['simulation_run_id'], ['simulation_runs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'round_number', name='uq_fl_rounds_session_round')
    )
    with op.batch_alter_table('federated_learning_rounds', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_federated_learning_rounds_session_id'), ['session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_federated_learning_rounds_simulation_run_id'), ['simulation_run_id'], unique=False)
        batch_op.create_index('ix_fl_rounds_round_num', ['round_number'], unique=False)

    # 2. Re-create child table: federated_learning_clients
    op.create_table(
        'federated_learning_clients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('samples_trained', sa.Integer(), nullable=False),
        sa.Column('local_loss', sa.Float(), nullable=False),
        sa.Column('local_accuracy', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['round_id'], ['federated_learning_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', 'client_id', name='uq_fl_client_round')
    )
    with op.batch_alter_table('federated_learning_clients', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_federated_learning_clients_round_id'), ['round_id'], unique=False)
        batch_op.create_index('ix_fl_clients_round_client', ['round_id', 'client_id'], unique=False)

