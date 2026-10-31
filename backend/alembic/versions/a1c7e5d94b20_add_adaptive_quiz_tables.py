"""add adaptive quiz tables

Revision ID: a1c7e5d94b20
Revises: 0fcc16ddc130
Create Date: 2026-10-31 10:00:00.000000

Adds the student practice / adaptive quiz data model:
concepts, concept_prerequisites, questions, quiz_attempts, question_attempts,
student_concept_level, student_concept_mastery, plus practice_submissions.student_id.

The 3 starter concepts and their prerequisite edges are inserted here so an
Alembic-only deployment has them. The curated question bank is seeded
idempotently by app.seed.quiz_seed (app start-up / `python -m app.cli.seed`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c7e5d94b20'
down_revision: Union[str, None] = '0fcc16ddc130'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


PURPOSES = ("practice", "diagnostic", "revision")


def upgrade() -> None:
    op.create_table(
        'concepts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('class_num', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('board', sa.String(length=20), nullable=False, server_default='TS'),
        sa.Column('chapter', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('class_num', 'subject', 'name', name='uq_concept_class_subject_name'),
        sa.CheckConstraint('class_num BETWEEN 1 AND 12', name='ck_concept_class_range'),
    )
    op.create_index('ix_concepts_id', 'concepts', ['id'])

    op.create_table(
        'concept_prerequisites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prerequisite_concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('concept_id', 'prerequisite_concept_id', name='uq_concept_prereq_pair'),
        sa.CheckConstraint('concept_id <> prerequisite_concept_id', name='ck_concept_prereq_not_self'),
    )
    op.create_index('ix_concept_prerequisites_concept_id', 'concept_prerequisites', ['concept_id'])
    op.create_index('ix_concept_prerequisites_prerequisite_concept_id', 'concept_prerequisites', ['prerequisite_concept_id'])

    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_objective', sa.Text(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('bloom_level', sa.String(length=20), nullable=False),
        sa.Column('question_type', sa.String(length=30), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=False),
        sa.Column('stem', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('correct_answer', sa.JSON(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('hint', sa.Text(), nullable=True),
        sa.Column('assessment_purpose', sa.String(length=20), nullable=False, server_default='practice'),
        sa.Column('distractor_misconceptions', sa.JSON(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('concept_id', 'content_hash', name='uq_question_concept_hash'),
        sa.CheckConstraint('level BETWEEN 1 AND 5', name='ck_question_level_range'),
        sa.CheckConstraint(_in('bloom_level', ('remember', 'understand', 'apply', 'analyze', 'evaluate')), name='ck_question_bloom'),
        sa.CheckConstraint(
            _in('question_type', ('mcq', 'multi_select', 'true_false', 'fill_blank', 'numerical', 'short_answer',
                                  'application', 'logical_reasoning', 'assertion_reasoning', 'step_by_step')),
            name='ck_question_type',
        ),
        sa.CheckConstraint(_in('difficulty', ('easy', 'medium', 'hard')), name='ck_question_difficulty'),
        sa.CheckConstraint(_in('assessment_purpose', PURPOSES), name='ck_question_purpose'),
        sa.CheckConstraint(_in('source', ('ai', 'curated')), name='ck_question_source'),
    )
    op.create_index('ix_questions_id', 'questions', ['id'])
    op.create_index('ix_questions_concept_id', 'questions', ['concept_id'])
    op.create_index('ix_questions_concept_level', 'questions', ['concept_id', 'level'])

    op.create_table(
        'quiz_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False, server_default='practice'),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('target_level', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='in_progress'),
        sa.Column('current_question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.CheckConstraint(_in('mode', PURPOSES), name='ck_quiz_attempt_mode'),
        sa.CheckConstraint(_in('status', ('in_progress', 'finished')), name='ck_quiz_attempt_status'),
        sa.CheckConstraint('current_level BETWEEN 1 AND 5', name='ck_quiz_attempt_level'),
    )
    op.create_index('ix_quiz_attempts_id', 'quiz_attempts', ['id'])
    op.create_index('ix_quiz_attempts_student_id', 'quiz_attempts', ['student_id'])
    op.create_index('ix_quiz_attempts_concept_id', 'quiz_attempts', ['concept_id'])
    op.create_index('ix_quiz_attempts_student_started', 'quiz_attempts', ['student_id', 'started_at'])

    op.create_table(
        'question_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quiz_attempt_id', sa.Integer(), sa.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('answer', sa.JSON(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('hints_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('attempt_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint('level BETWEEN 1 AND 5', name='ck_question_attempt_level'),
        sa.CheckConstraint('attempt_no >= 1', name='ck_question_attempt_no'),
    )
    op.create_index('ix_question_attempts_id', 'question_attempts', ['id'])
    op.create_index('ix_question_attempts_quiz_attempt_id', 'question_attempts', ['quiz_attempt_id'])
    op.create_index('ix_question_attempts_student_id', 'question_attempts', ['student_id'])
    op.create_index('ix_question_attempts_question_id', 'question_attempts', ['question_id'])
    op.create_index('ix_question_attempts_student_question', 'question_attempts', ['student_id', 'question_id'])

    op.create_table(
        'student_concept_level',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comfortable_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_level_reached', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('struggling_level', sa.Integer(), nullable=True),
        sa.Column('struggling_since', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('failed_counts', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('correct_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_level_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('possible_prerequisite_gap', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('prerequisite_gap_concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('student_id', 'concept_id', name='uq_student_concept_level'),
        sa.CheckConstraint('comfortable_level BETWEEN 1 AND 5', name='ck_scl_comfortable'),
        sa.CheckConstraint('max_level_reached BETWEEN 1 AND 5', name='ck_scl_max'),
        sa.CheckConstraint('struggling_level IS NULL OR struggling_level BETWEEN 1 AND 5', name='ck_scl_struggling'),
    )
    op.create_index('ix_scl_student', 'student_concept_level', ['student_id'])

    op.create_table(
        'student_concept_mastery',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('concept_id', sa.Integer(), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mastery_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='not_started'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('student_id', 'concept_id', name='uq_student_concept_mastery'),
        sa.CheckConstraint('mastery_score BETWEEN 0 AND 1', name='ck_mastery_range'),
        sa.CheckConstraint(
            _in('status', ('locked', 'not_started', 'learning', 'weak', 'needs_revision', 'mastered')),
            name='ck_mastery_status',
        ),
    )
    op.create_index('ix_scm_student', 'student_concept_mastery', ['student_id'])

    # Problem #7: practice submissions had no owner. Nullable so legacy rows survive.
    with op.batch_alter_table('practice_submissions') as batch_op:
        batch_op.add_column(sa.Column('student_id', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_practice_submissions_student_id', ['student_id'])

    # ---- starter concepts (frozen data) -------------------------------
    concepts = sa.table(
        'concepts',
        sa.column('id', sa.Integer), sa.column('class_num', sa.Integer), sa.column('subject', sa.String),
        sa.column('name', sa.String), sa.column('description', sa.Text), sa.column('board', sa.String),
        sa.column('chapter', sa.String),
    )
    op.bulk_insert(concepts, [
        {'id': 1, 'class_num': 6, 'subject': 'Mathematics', 'name': 'Integer Operations', 'board': 'TS',
         'chapter': 'Integers',
         'description': 'Adding, subtracting, multiplying and dividing positive and negative integers, including number-line reasoning and sign rules.'},
        {'id': 2, 'class_num': 7, 'subject': 'Mathematics', 'name': 'Algebraic Expressions', 'board': 'TS',
         'chapter': 'Algebraic Expressions',
         'description': 'Terms, coefficients, like terms, simplifying, adding/subtracting expressions and evaluating expressions by substitution.'},
        {'id': 3, 'class_num': 8, 'subject': 'Mathematics', 'name': 'Linear Equations', 'board': 'TS',
         'chapter': 'Linear Equations in One Variable',
         'description': 'Forming and solving linear equations in one variable, checking solutions and reasoning about methods.'},
    ])
    prereqs = sa.table(
        'concept_prerequisites',
        sa.column('concept_id', sa.Integer), sa.column('prerequisite_concept_id', sa.Integer),
    )
    op.bulk_insert(prereqs, [
        {'concept_id': 2, 'prerequisite_concept_id': 1},
        {'concept_id': 3, 'prerequisite_concept_id': 2},
    ])


def downgrade() -> None:
    with op.batch_alter_table('practice_submissions') as batch_op:
        batch_op.drop_index('ix_practice_submissions_student_id')
        batch_op.drop_column('student_id')
    op.drop_table('student_concept_mastery')
    op.drop_table('student_concept_level')
    op.drop_table('question_attempts')
    op.drop_table('quiz_attempts')
    op.drop_table('questions')
    op.drop_table('concept_prerequisites')
    op.drop_table('concepts')
