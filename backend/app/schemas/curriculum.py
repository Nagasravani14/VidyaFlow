from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# --- Syllabus Version ---
class SyllabusVersionBase(BaseModel):
    version_code: str
    academic_year: str
    description: Optional[str] = None
    is_current: bool = True


class SyllabusVersionRead(SyllabusVersionBase):
    id: int
    board_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Board ---
class BoardBase(BaseModel):
    code: str
    name: str
    full_name: Optional[str] = None
    country: str = "India"
    state_or_region: Optional[str] = None
    is_active: bool = True


class BoardRead(BoardBase):
    id: int
    created_at: datetime
    syllabus_versions: List[SyllabusVersionRead] = []
    model_config = ConfigDict(from_attributes=True)


# --- ClassGrade ---
class ClassGradeBase(BaseModel):
    grade_number: int
    code: str
    name: str
    stage: str = "Secondary"


class ClassGradeRead(ClassGradeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Learning Objective ---
class LearningObjectiveBase(BaseModel):
    code: str
    description: str
    bloom_taxonomy_level: str = "understand"
    order_index: int = 1


class LearningObjectiveRead(LearningObjectiveBase):
    id: int
    chapter_id: Optional[int] = None
    topic_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# --- Topic ---
class TopicBase(BaseModel):
    topic_code: str
    title: str
    description: Optional[str] = None
    order_index: int = 1
    estimated_minutes: int = 30
    verification_status: str = "verified"


class TopicSummary(TopicBase):
    id: int
    chapter_id: int
    parent_topic_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# --- Chapter ---
class ChapterBase(BaseModel):
    chapter_number: int
    code: str
    title: str
    description: Optional[str] = None
    estimated_minutes: int = 90
    order_index: int = 1
    verification_status: str = "verified"


class ChapterSummary(ChapterBase):
    id: int
    subject_id: int
    topic_count: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class ChapterDetail(ChapterBase):
    id: int
    subject_id: int
    topics: List[TopicSummary] = []
    learning_objectives: List[LearningObjectiveRead] = []
    model_config = ConfigDict(from_attributes=True)


# --- Subject ---
class SubjectBase(BaseModel):
    code: str
    name: str
    category: str = "STEM"
    description: Optional[str] = None


class SubjectSummary(SubjectBase):
    id: int
    board_id: int
    class_id: int
    class_grade_number: Optional[int] = None
    syllabus_version_id: Optional[int] = None
    chapter_count: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class SubjectDetail(SubjectSummary):
    chapters: List[ChapterSummary] = []
    model_config = ConfigDict(from_attributes=True)
