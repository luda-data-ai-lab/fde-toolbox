"""rename CoachQ tables to DiscoveryQ

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASE = ['id', 'tenant_id', 'created_at', 'updated_at', 'created_by']
TABLES = {
    'custom_questions': ['engagement_id', 'category', 'text', 'tags', 'audience', 'follow_ups', 'source_ref'],
    'subjects': ['engagement_id', 'name', 'department', 'job_title', 'system_ids', 'notes'],
    'sessions': ['engagement_id', 'type', 'subject_id', 'title', 'session_date', 'status', 'summary'],
    'session_questions': [
        'session_id', 'question_ref', 'custom_question_id', 'custom_text', 'text', 'category', 'follow_ups', 'answer',
        'position',
    ],
    'insights': ['session_id', 'session_question_id', 'text', 'tags'],
    'action_items': ['session_id', 'insight_id', 'title', 'assignee', 'due', 'status'],
}
SOURCE_TYPES = {'coach': 'coach_session', 'discovery': 'discovery_session'}


def _create(p: str) -> None:
        op.create_table(f'{p}_custom_questions',
        sa.Column('engagement_id', sa.String(length=36), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('audience', sa.JSON(), nullable=False),
        sa.Column('follow_ups', sa.JSON(), nullable=False),
        sa.Column('source_ref', sa.JSON(), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f(f'fk_{p}_custom_questions_engagement_id_engagements'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_custom_questions_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_custom_questions'))
        )
        with op.batch_alter_table(f'{p}_custom_questions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_custom_questions_engagement_id'), ['engagement_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_custom_questions_tenant_id'), ['tenant_id'], unique=False)

        op.create_table(f'{p}_subjects',
        sa.Column('engagement_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('job_title', sa.String(length=100), nullable=True),
        sa.Column('system_ids', sa.JSON(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f(f'fk_{p}_subjects_engagement_id_engagements'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_subjects_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_subjects'))
        )
        with op.batch_alter_table(f'{p}_subjects', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_subjects_engagement_id'), ['engagement_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_subjects_tenant_id'), ['tenant_id'], unique=False)

        op.create_table(f'{p}_sessions',
        sa.Column('engagement_id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('session_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], name=op.f(f'fk_{p}_sessions_engagement_id_engagements'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], [f'{p}_subjects.id'], name=op.f(f'fk_{p}_sessions_subject_id_{p}_subjects'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_sessions_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_sessions'))
        )
        with op.batch_alter_table(f'{p}_sessions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_sessions_engagement_id'), ['engagement_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_sessions_subject_id'), ['subject_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_sessions_tenant_id'), ['tenant_id'], unique=False)

        op.create_table(f'{p}_session_questions',
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('question_ref', sa.JSON(), nullable=True),
        sa.Column('custom_question_id', sa.String(length=36), nullable=True),
        sa.Column('custom_text', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('follow_ups', sa.JSON(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['custom_question_id'], [f'{p}_custom_questions.id'], name=op.f(f'fk_{p}_session_questions_custom_question_id_{p}_custom_questions'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], [f'{p}_sessions.id'], name=op.f(f'fk_{p}_session_questions_session_id_{p}_sessions'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_session_questions_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_session_questions'))
        )
        with op.batch_alter_table(f'{p}_session_questions', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_session_questions_custom_question_id'), ['custom_question_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_session_questions_session_id'), ['session_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_session_questions_tenant_id'), ['tenant_id'], unique=False)

        op.create_table(f'{p}_insights',
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('session_question_id', sa.String(length=36), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], [f'{p}_sessions.id'], name=op.f(f'fk_{p}_insights_session_id_{p}_sessions'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_question_id'], [f'{p}_session_questions.id'], name=op.f(f'fk_{p}_insights_session_question_id_{p}_session_questions'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_insights_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_insights'))
        )
        with op.batch_alter_table(f'{p}_insights', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_insights_session_id'), ['session_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_insights_session_question_id'), ['session_question_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_insights_tenant_id'), ['tenant_id'], unique=False)

        op.create_table(f'{p}_action_items',
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('insight_id', sa.String(length=36), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('assignee', sa.String(length=100), nullable=True),
        sa.Column('due', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['insight_id'], [f'{p}_insights.id'], name=op.f(f'fk_{p}_action_items_insight_id_{p}_insights'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], [f'{p}_sessions.id'], name=op.f(f'fk_{p}_action_items_session_id_{p}_sessions'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f(f'fk_{p}_action_items_tenant_id_tenants'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f(f'pk_{p}_action_items'))
        )
        with op.batch_alter_table(f'{p}_action_items', schema=None) as batch_op:
            batch_op.create_index(batch_op.f(f'ix_{p}_action_items_insight_id'), ['insight_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_action_items_session_id'), ['session_id'], unique=False)
            batch_op.create_index(batch_op.f(f'ix_{p}_action_items_tenant_id'), ['tenant_id'], unique=False)


def _move(old: str, new: str) -> None:
    for name, cols in TABLES.items():
        names = ', '.join(cols + BASE)
        op.execute(f'INSERT INTO {new}_{name} ({names}) SELECT {names} FROM {old}_{name}')
    for name in reversed(TABLES):
        op.drop_table(f'{old}_{name}')
    for table in ('onto_candidates', 'onto_terms'):
        op.execute(
            sa.text(f'UPDATE {table} SET source_type = :new WHERE source_type = :old').bindparams(
                new=SOURCE_TYPES[new], old=SOURCE_TYPES[old]
            )
        )


def upgrade() -> None:
    _create('discovery')
    _move('coach', 'discovery')


def downgrade() -> None:
    _create('coach')
    _move('discovery', 'coach')
