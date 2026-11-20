"""
b2c3d4e5f6a7_create_network_topology_tables.py

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-17 23:00:00.000000

Objective: Create Phase 5 Network Topology tables for authentic NS-3 node coordinates
and physical network connectivity edges:
1. network_node_coordinates
2. network_edges
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Table: network_node_coordinates
    if 'network_node_coordinates' not in tables:
        op.create_table(
            'network_node_coordinates',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('simulation_run_id', sa.Integer(), nullable=False),
            sa.Column('node_id', sa.Integer(), nullable=False),
            sa.Column('x_coord', sa.Float(), nullable=False),
            sa.Column('y_coord', sa.Float(), nullable=False),
            sa.Column('z_coord', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['simulation_run_id'], ['simulation_runs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('simulation_run_id', 'node_id', name='uq_node_coordinates_run_node')
        )
        with op.batch_alter_table('network_node_coordinates', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_network_node_coordinates_simulation_run_id'), ['simulation_run_id'], unique=False)
            batch_op.create_index('ix_node_coords_run_node', ['simulation_run_id', 'node_id'], unique=False)

    # 2. Table: network_edges
    if 'network_edges' not in tables:
        op.create_table(
            'network_edges',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('simulation_run_id', sa.Integer(), nullable=False),
            sa.Column('source_node', sa.Integer(), nullable=False),
            sa.Column('target_node', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.ForeignKeyConstraint(['simulation_run_id'], ['simulation_runs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('simulation_run_id', 'source_node', 'target_node', name='uq_network_edges_run_src_tgt')
        )
        with op.batch_alter_table('network_edges', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_network_edges_simulation_run_id'), ['simulation_run_id'], unique=False)
            batch_op.create_index('ix_network_edges_run_src', ['simulation_run_id', 'source_node'], unique=False)
            batch_op.create_index('ix_network_edges_run_tgt', ['simulation_run_id', 'target_node'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Drop network_edges
    if 'network_edges' in tables:
        indexes_e = [idx['name'] for idx in inspector.get_indexes('network_edges')]
        with op.batch_alter_table('network_edges', schema=None) as batch_op:
            if 'ix_network_edges_run_tgt' in indexes_e:
                batch_op.drop_index('ix_network_edges_run_tgt')
            if 'ix_network_edges_run_src' in indexes_e:
                batch_op.drop_index('ix_network_edges_run_src')
            if 'ix_network_edges_simulation_run_id' in indexes_e:
                batch_op.drop_index('ix_network_edges_simulation_run_id')
        op.drop_table('network_edges')

    # 2. Drop network_node_coordinates
    if 'network_node_coordinates' in tables:
        indexes_n = [idx['name'] for idx in inspector.get_indexes('network_node_coordinates')]
        with op.batch_alter_table('network_node_coordinates', schema=None) as batch_op:
            if 'ix_node_coords_run_node' in indexes_n:
                batch_op.drop_index('ix_node_coords_run_node')
            if 'ix_network_node_coordinates_simulation_run_id' in indexes_n:
                batch_op.drop_index('ix_network_node_coordinates_simulation_run_id')
        op.drop_table('network_node_coordinates')
