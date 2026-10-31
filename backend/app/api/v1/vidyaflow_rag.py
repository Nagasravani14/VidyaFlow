"""
VidyaFlow - RAG Endpoints Router
Implements all Student, Teacher, Chatbot, and Parent Dashboard APIs
using local ChromaDB RAG and Dual LLM Engine (Gemini / Groq).
Built with robust, fail-safe exception handling so endpoints ALWAYS return HTTP 200.
"""

import logging
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.services.vector_store import ChromaVectorStore, normalize_board
from app.services.llm_engine import LLMEngine

logger = logging.getLogger("vidyaflow.rag_router")

router = APIRouter(tags=["VidyaFlow RAG & LLM Engine"])

# Dependency providers
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore.get_instance()

def get_llm_engine() -> LLMEngine:
    return LLMEngine()


# =============================================================================
# Request & Response Schemas
# =============================================================================

# --- Adaptive Assessment Models (Master Prompt Schema) ---
class QuizOption(BaseModel):
    option_id: str
    text: str

class QuizQuestion(BaseModel):
    question_id: str
    question_type: Literal["mcq", "fill_blank", "conceptual_short"]
    cognitive_level: Literal["recall", "understanding", "application", "analysis"]
    difficulty: Literal["easy", "medium", "hard"]
    question_text: str
    options: List[QuizOption]
    correct_answer: str
    hint: str
    explanation: str
    prerequisite_concept_tested: str
    root_gap_remediation: str

class QuizResponse(BaseModel):
    concept_id: str
    difficulty_level: str
    total_questions: int
    questions: List[QuizQuestion]

class AdaptiveQuizRequest(BaseModel):
    board: str = Field(default="ICSE", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=9, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Physics", description="Subject name")
    chapter: str = Field(default="Light", description="Chapter or topic title")
    concept: Optional[str] = Field(default=None, description="Specific target concept")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", description="Target difficulty")
    num_questions: int = Field(default=5, ge=1, le=20, description="Number of adaptive questions")
    prerequisite_list: Optional[List[str]] = Field(default=None, description="Prerequisite concepts")
    focus_skills: Optional[List[str]] = Field(default=None, description="Focus cognitive skills")

class QuizGenerateRequest(BaseModel):
    board: str = Field(default="ICSE", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=9, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Physics", description="Subject name")
    chapter: str = Field(default="Light", description="Chapter or topic title")
    count: int = Field(default=10, ge=1, le=20, description="Number of MCQs to generate (10-20)")


class QuizQuestionItem(BaseModel):
    id: str
    question: str
    options: List[str]
    correct_option_index: int
    correct_option: str
    solution: str


class QuizEvaluateRequest(BaseModel):
    question_id: str
    selected_option: str
    correct_option: str


class QuizEvaluateResponse(BaseModel):
    question_id: str
    correct: bool
    selected_option: str
    correct_option: str
    explanation: str
    score_delta: int = 1
    total_score: int = 1


class WorksheetCounts(BaseModel):
    mcq: int = Field(default=5, ge=0, le=20)
    short_answer: int = Field(default=3, ge=0, le=15)
    long_answer: int = Field(default=2, ge=0, le=10)


class WorksheetRequest(BaseModel):
    board: str = Field(default="TS", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=8, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Mathematics", description="Subject name")
    chapter: str = Field(default="Algebra", description="Chapter or unit title")
    difficulty: str = Field(default="Medium", description="Easy, Medium, or Hard")
    counts: Optional[WorksheetCounts] = None


class ChatAskRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Student's syllabus doubt or question")
    board: str = Field(default="ICSE", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=7, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Biology", description="Subject name")


class ChatAskResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)


class LessonContextRequest(BaseModel):
    board: str = Field(default="TS", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=8, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Mathematics", description="Subject name")
    chapter: str = Field(default="Algebra", description="Chapter or topic title")


class ConceptCardItem(BaseModel):
    id: str
    title: str
    summary: str
    definition: Optional[str] = None
    formula: Optional[str] = None
    real_world_example: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    formulas_or_definitions: List[str] = Field(default_factory=list)
    source_reference: Optional[str] = None


class LessonOverviewResponse(BaseModel):
    chapter: str
    subject: str
    board: str
    class_num: int
    chapter_summary: Optional[str] = None
    key_concepts: Optional[List[ConceptCardItem]] = None
    concept_cards: List[ConceptCardItem]
    prescribed_next_step: str
    recommended_learning_path: List[str]


class FlashcardItem(BaseModel):
    id: str
    front: str
    back: str
    concept_tag: str = Field(default="General")
    concept: Optional[str] = None
    summary: Optional[str] = None


class TeacherAssignmentRequest(BaseModel):
    board: str = Field(default="TS", description="Board identifier: TS or ICSE")
    class_num: int = Field(default=8, ge=6, le=10, description="Class grade (6-10)")
    subject: str = Field(default="Mathematics", description="Subject name")
    chapter: str = Field(default="Algebraic Expressions and Identities", description="Chapter or topic title")
    difficulty: str = Field(default="Medium", description="Easy, Medium, or Hard")
    assignment_title: Optional[str] = None


class TeacherAssignmentResponse(BaseModel):
    assignment_id: str
    title: str
    board: str
    class_num: int
    subject: str
    chapter: str
    difficulty: str
    total_marks: int = 25
    estimated_duration_minutes: int = 45
    instructions: List[str] = Field(default_factory=list)
    section_a: List[Dict[str, Any]]
    section_b: List[Dict[str, Any]]
    section_c: List[Dict[str, Any]]
    section_a_mcqs: List[Dict[str, Any]]
    section_b_short_answers: List[Dict[str, Any]]
    section_c_hots: List[Dict[str, Any]]
    teacher_answer_key: Dict[str, Any]
    grading_rubric: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None


# =============================================================================
# A) STUDENT MODE - Interactive Quiz Engine
# =============================================================================

@router.post("/quiz/generate", response_model=List[QuizQuestionItem])
def generate_quiz(
    req: QuizGenerateRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Queries ChromaDB using exact board/class/chapter filters, retrieves textbook snippets,
    and sends them to the LLM to generate 10 to 20 MCQs with options, correct answer index,
    and step-by-step solutions. Always returns HTTP 200 with complete coverage.
    """
    try:
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} fundamental concepts and definitions",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=8,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /quiz/generate: {e}")

        questions = llm.generate_quiz(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            count=req.count,
            context_chunks=context_snippets,
        )
        return questions
    except Exception as e:
        logger.exception(f"Unexpected error in /quiz/generate: {e}")
        return llm._fallback_quiz_generator(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            count=req.count,
            context_chunks=[],
        )


@router.post("/quiz/adaptive/generate", response_model=QuizResponse)
def generate_adaptive_quiz(
    req: AdaptiveQuizRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    VidyaFlow Adaptive Quiz & Assessment Engine:
    Generates non-repetitive, high-diversity questions (MCQs, Fill-in-the-Blank, Short Conceptual)
    grounded in official textbook context with cognitive depth breakdown and prerequisite gap tagging.
    """
    concept_target = req.concept or req.chapter
    try:
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} {concept_target} core definitions formulas theorems applications",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=6,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /quiz/adaptive/generate: {e}")

        context_str = "\n\n---\n\n".join(context_snippets) if context_snippets else f"{req.board} Board Class {req.class_num} {req.subject} - {req.chapter} ({concept_target})"

        return llm.generate_adaptive_quiz(
            board=normalize_board(req.board),
            class_level=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            concept=concept_target,
            rag_context=context_str,
            difficulty=req.difficulty,
            num_questions=req.num_questions,
            prerequisite_list=req.prerequisite_list,
            focus_skills=req.focus_skills,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in /quiz/adaptive/generate: {e}")
        return llm._fallback_adaptive_quiz(
            board=normalize_board(req.board),
            class_level=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            concept=concept_target,
            difficulty=req.difficulty,
            num_questions=req.num_questions,
            prerequisite_list=req.prerequisite_list or ["Foundational Concepts"],
            focus_skills=req.focus_skills or ["definition", "application"],
        )


@router.post("/quiz/evaluate", response_model=QuizEvaluateResponse)
def evaluate_quiz(
    req: QuizEvaluateRequest,
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Validates student's answer, returns instant correctness status ("correct": true/false),
    explanation, and score updates. Guaranteed zero-failure.
    """
    try:
        return llm.evaluate_quiz_answer(
            question_id=req.question_id,
            selected_option=req.selected_option,
            correct_option=req.correct_option,
        )
    except Exception as e:
        logger.warning(f"Evaluation fallback used: {e}")
        is_corr = req.selected_option.strip().lower() == req.correct_option.strip().lower()
        return QuizEvaluateResponse(
            question_id=req.question_id,
            correct=is_corr,
            selected_option=req.selected_option,
            correct_option=req.correct_option,
            explanation="Correct!" if is_corr else f"The correct option is: {req.correct_option}",
            score_delta=1 if is_corr else 0,
            total_score=1 if is_corr else 0,
        )


# =============================================================================
# B) TEACHER MODE - Worksheet Generator
# =============================================================================

@router.post("/teacher/worksheet")
def generate_worksheet(
    req: WorksheetRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Retrieves textbook context via RAG and prompts the LLM to build a print-ready
    worksheet split into sections (Section A: MCQs, Section B: Short Answer, Section C: Long Answer),
    complete with a separate Teacher Answer Key.
    """
    try:
        counts_dict = req.counts.model_dump() if req.counts else {"mcq": 5, "short_answer": 3, "long_answer": 2}
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} problems formulas examples exercises",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=6,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /teacher/worksheet: {e}")

        return llm.generate_worksheet(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            difficulty=req.difficulty,
            counts=counts_dict,
            context_chunks=context_snippets,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in /teacher/worksheet: {e}")
        return llm._fallback_worksheet(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            difficulty=req.difficulty,
            counts=req.counts.model_dump() if req.counts else {"mcq": 5, "short_answer": 3, "long_answer": 2},
        )


# =============================================================================
# C) AI CHATBOT (Syllabus Doubt Resolver)
# =============================================================================

@router.post("/chat/ask", response_model=ChatAskResponse)
def ask_chatbot(
    req: ChatAskRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Performs vector search matching the board/class context and answers the student's question
    strictly using textbook data to prevent hallucinations.
    """
    try:
        retrieved = []
        try:
            retrieved = vector_store.query_curriculum(
                query=req.question,
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                n_results=4,
            )
        except Exception as e:
            logger.warning(f"Vector search error in /chat/ask: {e}")

        res = llm.answer_doubt(
            question=req.question,
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            retrieved_passages=retrieved,
        )
        return ChatAskResponse(
            answer=res.get("answer", "Please refer to your textbook for further reading."),
            sources=res.get("sources", [f"{req.board} Class {req.class_num} {req.subject}"]),
        )
    except Exception as e:
        logger.exception(f"Error in /chat/ask: {e}")
        return ChatAskResponse(
            answer=f"Based on {req.board} Board Class {req.class_num} syllabus for {req.subject}: please verify the fundamental definition and formulas for {req.question}.",
            sources=[f"{req.board} Class {req.class_num} {req.subject}"],
        )


# =============================================================================
# D) PARENT MODE & DASHBOARD DATA
# =============================================================================

@router.get("/dashboard/stats")
def get_dashboard_stats():
    """
    Returns structured JSON containing student quiz performance history,
    weak chapters, total study time, and completed assignments for Parent/Student dashboard.
    """
    return {
        "student_profile": {
            "name": "Arjun Rao",
            "student_id": "VF-2026-9042",
            "board": "ICSE",
            "class_grade": 9,
            "school": "Hyderabad Public School",
            "academic_year": "2026-2027",
        },
        "study_overview": {
            "total_study_time_hours": 34.5,
            "weekly_study_time_hours": 6.2,
            "total_quizzes_completed": 18,
            "overall_accuracy_percentage": 84.5,
            "attendance_rate_percentage": 96.0,
            "streak_days": 12,
        },
        "weak_chapters": [
            {
                "subject": "Physics",
                "chapter": "Refraction of Light at Plane Surfaces",
                "board": "ICSE",
                "class": 9,
                "mastery_score_pct": 52.0,
                "recommended_focus": "Critical angle and Snell's Law calculations",
                "status": "Needs Review",
            },
            {
                "subject": "Mathematics",
                "chapter": "Algebraic Identities & Factorization",
                "board": "TS",
                "class": 8,
                "mastery_score_pct": 61.5,
                "recommended_focus": "Splitting the middle term in quadratic polynomials",
                "status": "In Progress",
            },
        ],
        "strong_chapters": [
            {
                "subject": "Biology",
                "chapter": "Nutrition in Plants - Photosynthesis",
                "board": "ICSE",
                "class": 7,
                "mastery_score_pct": 94.0,
                "status": "Mastered",
            },
            {
                "subject": "Mathematics",
                "chapter": "Knowing Our Numbers",
                "board": "TS",
                "class": 6,
                "mastery_score_pct": 91.0,
                "status": "Mastered",
            },
            {
                "subject": "Chemistry",
                "chapter": "Periodic Table & Periodic Properties",
                "board": "ICSE",
                "class": 10,
                "mastery_score_pct": 88.5,
                "status": "Mastered",
            },
        ],
        "completed_assignments": [
            {
                "id": "asg_101",
                "title": "Class 9 Physics Worksheet: Light & Refraction",
                "subject": "Physics",
                "date_completed": "2026-10-29",
                "score": "18/20",
                "percentage": 90.0,
                "teacher_feedback": "Excellent ray diagrams and conceptual clarity.",
            },
            {
                "id": "asg_102",
                "title": "Class 8 Mathematics Practice Set: Linear Equations",
                "subject": "Mathematics",
                "date_completed": "2026-10-27",
                "score": "14/15",
                "percentage": 93.3,
                "teacher_feedback": "Accurate transpositions throughout.",
            },
            {
                "id": "asg_103",
                "title": "Class 7 Biology Quiz: Photosynthesis & Chloroplasts",
                "subject": "Biology",
                "date_completed": "2026-10-25",
                "score": "5/5",
                "percentage": 100.0,
                "teacher_feedback": "Flawless explanation of light and dark reactions.",
            },
        ],
        "recent_quiz_history": [
            {"date": "2026-10-30", "subject": "Physics", "chapter": "Light", "score": 4, "total": 5, "percentage": 80.0},
            {"date": "2026-10-28", "subject": "Mathematics", "chapter": "Algebra", "score": 5, "total": 5, "percentage": 100.0},
            {"date": "2026-10-26", "subject": "Biology", "chapter": "Photosynthesis", "score": 5, "total": 5, "percentage": 100.0},
            {"date": "2026-10-23", "subject": "Mathematics", "chapter": "Knowing Our Numbers", "score": 5, "total": 5, "percentage": 100.0},
        ],
    }


# =============================================================================
# E) LESSON OVERVIEW & FLASHCARDS
# =============================================================================

@router.post("/lesson/overview", response_model=LessonOverviewResponse)
def get_lesson_overview(
    req: LessonContextRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Returns structured 3-paragraph chapter summary, 5-8 detailed AI concept breakdown cards,
    prescribed next step, and recommended learning path. Guaranteed HTTP 200.
    """
    try:
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} key concepts theory definitions formulas summary",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=6,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /lesson/overview: {e}")

        return llm.generate_lesson_overview(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            context_chunks=context_snippets,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in /lesson/overview: {e}")
        return llm._fallback_lesson_overview(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            context_chunks=[],
        )


@router.post("/lesson/flashcards", response_model=List[FlashcardItem])
def get_lesson_flashcards(
    req: LessonContextRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    Returns an array of 8-10 interactive flashcards (id, front, back, concept_tag, summary)
    grounded in official textbook context. Guaranteed HTTP 200.
    """
    try:
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} important terms definitions laws formulas quiz questions",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=5,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /lesson/flashcards: {e}")

        return llm.generate_flashcards(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            context_chunks=context_snippets,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in /lesson/flashcards: {e}")
        return llm._fallback_flashcards(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            context_chunks=[],
        )


# =============================================================================
# F) ONE-CLICK TEACHER ASSIGNMENT GENERATOR
# =============================================================================

@router.post("/teacher/assignment", response_model=TeacherAssignmentResponse)
def generate_teacher_assignment(
    req: TeacherAssignmentRequest,
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    llm: LLMEngine = Depends(get_llm_engine),
):
    """
    With a single click, retrieves textbook context via RAG and generates a complete,
    ready-to-assign 25-mark examination packet split into:
    - Section A: 5 MCQs (1 mark each = 5 marks)
    - Section B: 5 Short Answer Questions (2 marks each = 10 marks)
    - Section C: 2 HOTS / Application Questions (5 marks each = 10 marks)
    - Automated Teacher Answer Key with detailed step-by-step marking rubrics.
    Guaranteed HTTP 200.
    """
    try:
        context_snippets = []
        try:
            retrieved = vector_store.query_curriculum(
                query=f"{req.subject} {req.chapter} problems formulas examples definitions questions",
                board=req.board,
                class_num=req.class_num,
                subject=req.subject,
                chapter=req.chapter,
                n_results=6,
            )
            context_snippets = [item["text"] for item in retrieved if item.get("text")]
        except Exception as e:
            logger.warning(f"Vector search warning in /teacher/assignment: {e}")

        result = llm.generate_teacher_assignment(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            difficulty=req.difficulty,
            assignment_title=req.assignment_title,
            context_chunks=context_snippets,
        )
        return result
    except Exception as e:
        logger.exception(f"Unexpected error in /teacher/assignment: {e}")
        title = req.assignment_title or f"Class {req.class_num} {req.subject} Assessment: {req.chapter}"
        return llm._fallback_teacher_assignment(
            board=normalize_board(req.board),
            class_num=req.class_num,
            subject=req.subject,
            chapter=req.chapter,
            difficulty=req.difficulty,
            title=title,
        )
