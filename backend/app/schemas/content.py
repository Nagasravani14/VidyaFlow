from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.curriculum import TopicSummary, LearningObjectiveRead


# --- Source Attribution ---
class SourceAttributionBase(BaseModel):
    source_type: str = "official_textbook"
    publisher: str
    publication_year: Optional[int] = None
    edition: Optional[str] = None
    title: str
    page_reference: Optional[str] = None
    license_or_permission_status: str = "public_curriculum_framework"
    verification_status: str = "verified"
    verified_by: Optional[str] = None


class SourceAttributionRead(SourceAttributionBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Lesson ---
class LessonBase(BaseModel):
    section_type: str = "explanation"  # explanation, key_concepts, recap, summary
    title: str
    content: str
    summary: Optional[str] = None
    language: str = "en"
    reading_time_minutes: int = 5
    order_index: int = 1
    verification_status: str = "verified"


class LessonRead(LessonBase):
    id: int
    topic_id: int
    source_attribution_id: Optional[int] = None
    syllabus_version_id: Optional[int] = None
    source_attribution: Optional[SourceAttributionRead] = None
    model_config = ConfigDict(from_attributes=True)


# --- Worked Example ---
class WorkedExampleBase(BaseModel):
    example_number: int = 1
    problem_statement: str
    step_by_step_solution: str
    verification_step: Optional[str] = None
    key_takeaway: Optional[str] = None
    language: str = "en"
    verification_status: str = "verified"


class WorkedExampleRead(WorkedExampleBase):
    id: int
    topic_id: int
    source_attribution_id: Optional[int] = None
    source_attribution: Optional[SourceAttributionRead] = None
    model_config = ConfigDict(from_attributes=True)


# --- Question Option ---
class QuestionOptionBase(BaseModel):
    option_index: int
    option_text: str
    is_correct: bool = False
    feedback: Optional[str] = None


class QuestionOptionRead(QuestionOptionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Practice Question ---
class PracticeQuestionBase(BaseModel):
    question_code: str
    question_text: str
    question_type: str = "multiple_choice"
    difficulty_level: str = "medium"
    marks: int = 1
    hint: Optional[str] = None
    worked_explanation: str
    correct_answer: str
    language: str = "en"
    verification_status: str = "verified"


class PracticeQuestionRead(PracticeQuestionBase):
    id: int
    topic_id: int
    options: List[QuestionOptionRead] = []
    source_attribution_id: Optional[int] = None
    source_attribution: Optional[SourceAttributionRead] = None
    model_config = ConfigDict(from_attributes=True)


# --- Prerequisite Relationship ---
class PrerequisiteRelationshipRead(BaseModel):
    id: int
    target_topic_id: int
    prerequisite_topic_id: int
    relationship_type: str
    description: Optional[str] = None
    prerequisite_topic: Optional[TopicSummary] = None
    model_config = ConfigDict(from_attributes=True)


# --- Topic Detail (with lessons, examples, objectives, prerequisites) ---
class TopicDetail(TopicSummary):
    learning_objectives: List[LearningObjectiveRead] = []
    lessons: List[LessonRead] = []
    worked_examples: List[WorkedExampleRead] = []
    prerequisites: List[PrerequisiteRelationshipRead] = []
    model_config = ConfigDict(from_attributes=True)
