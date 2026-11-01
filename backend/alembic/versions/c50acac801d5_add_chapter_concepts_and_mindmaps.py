"""add_chapter_concepts_and_mindmaps

Revision ID: c50acac801d5
Revises: a1c7e5d94b20
Create Date: 2026-11-01 15:18:14.997574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c50acac801d5'
down_revision: Union[str, None] = 'a1c7e5d94b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create chapter_mindmaps table
    op.create_table(
        'chapter_mindmaps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chapter_id', sa.Integer(), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('mindmap_json', sa.JSON(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='ai'),
        sa.Column('review_status', sa.String(length=20), nullable=False, server_default='unreviewed'),
        sa.Column('grounded', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('chapter_id', name='uq_chapter_mindmaps_chapter_id'),
        sa.CheckConstraint("source IN ('ai', 'curated')", name='ck_chapter_mindmap_source'),
        sa.CheckConstraint("review_status IN ('unreviewed', 'approved', 'rejected')", name='ck_chapter_mindmap_review_status'),
    )
    op.create_index('ix_chapter_mindmaps_id', 'chapter_mindmaps', ['id'])
    op.create_index('ix_chapter_mindmaps_chapter_id', 'chapter_mindmaps', ['chapter_id'])
    op.create_index('ix_chapter_mindmaps_review_status', 'chapter_mindmaps', ['review_status'])

    # 2. Add chapter_id to concepts and update unique constraint
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chapter_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_concepts_chapter_id', 'chapters', ['chapter_id'], ['id'], ondelete='SET NULL')
        batch_op.create_unique_constraint('uq_concept_chapter_id', ['chapter_id'])
        batch_op.create_index('ix_concepts_chapter_id', ['chapter_id'])
        batch_op.drop_constraint('uq_concept_class_subject_name', type_='unique')
        batch_op.create_unique_constraint('uq_concept_board_class_subject_name', ['board', 'class_num', 'subject', 'name'])

    # 3. Add review_status to questions
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('review_status', sa.String(length=20), nullable=False, server_default='unreviewed'))
        batch_op.create_check_constraint('ck_question_review_status', "review_status IN ('unreviewed', 'approved', 'rejected')")
        batch_op.create_index('ix_questions_review_status', ['review_status'])

    # Set existing curated questions to 'approved'
    op.execute("UPDATE questions SET review_status = 'approved' WHERE source = 'curated'")


def downgrade() -> None:
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_constraint('ck_question_review_status', type_='check')
        batch_op.drop_index('ix_questions_review_status')
        batch_op.drop_column('review_status')

    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_concept_board_class_subject_name', type_='unique')
        batch_op.create_unique_constraint('uq_concept_class_subject_name', ['class_num', 'subject', 'name'])
        batch_op.drop_index('ix_concepts_chapter_id')
        batch_op.drop_constraint('uq_concept_chapter_id', type_='unique')
        batch_op.drop_constraint('fk_concepts_chapter_id', type_='foreignkey')
        batch_op.drop_column('chapter_id')

    op.drop_index('ix_chapter_mindmaps_review_status', table_name='chapter_mindmaps')
    op.drop_index('ix_chapter_mindmaps_chapter_id', table_name='chapter_mindmaps')
    op.drop_index('ix_chapter_mindmaps_id', table_name='chapter_mindmaps')
    op.drop_table('chapter_mindmaps')
