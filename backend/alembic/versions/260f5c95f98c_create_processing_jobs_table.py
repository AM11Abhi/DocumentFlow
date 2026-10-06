"""create processing_jobs table

Revision ID: 260f5c95f98c
Revises: b8890c4302b4
Create Date: 2026-10-04 16:12:15.974421

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '260f5c95f98c'
down_revision: Union[str, Sequence[str], None] = 'b8890c4302b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to existing document_status_enum in PostgreSQL if not present
    op.execute("ALTER TYPE document_status_enum ADD VALUE IF NOT EXISTS 'PROCESSING'")
    op.execute("ALTER TYPE document_status_enum ADD VALUE IF NOT EXISTS 'COMPLETED'")
    op.execute("ALTER TYPE document_status_enum ADD VALUE IF NOT EXISTS 'FAILED'")

    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'QUEUED',
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                name='job_status_enum',
            ),
            nullable=False,
        ),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['document_id'], ['documents.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
    )


def downgrade() -> None:
    op.drop_table('processing_jobs')
    op.execute("DROP TYPE IF EXISTS job_status_enum")
