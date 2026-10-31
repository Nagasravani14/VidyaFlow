import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from google import genai
from google.genai import errors as genai_errors
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini service errors."""
    def __init__(self, message: str, status_code: int = 500, error_type: str = "gemini_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class GeminiAuthError(GeminiError):
    """Raised when the Gemini API key is missing, invalid, or unauthorized."""
    def __init__(self, message: str = "Invalid or unconfigured Gemini API key."):
        super().__init__(message, status_code=401, error_type="auth_error")


class GeminiQuotaError(GeminiError):
    """Raised when API rate limits or resource quotas are exhausted."""
    def __init__(
        self,
        message: str = "Gemini API quota exceeded or rate limit reached.",
        retry_after_seconds: Optional[int] = None,
        is_daily_exhaustion: bool = False,
    ):
        super().__init__(message, status_code=429, error_type="quota_error")
        self.retry_after_seconds = retry_after_seconds
        self.is_daily_exhaustion = is_daily_exhaustion


class GeminiResponseError(GeminiError):
    """Raised when the model response is malformed, blocked, or fails validation."""
    def __init__(self, message: str = "Failed to parse or validate Gemini model response."):
        super().__init__(message, status_code=502, error_type="response_error")


# --- Structured Output Pydantic Schemas ---

class CitationRef(BaseModel):
    source_title: str
    page_number: int
    heading: Optional[str] = None
    excerpt: Optional[str] = None


class TutorExplanation(BaseModel):
    explanation: str
    key_points: List[str] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)
    is_textbook_grounded: bool = True
    grounding_notes: str = ""
    citations: List[CitationRef] = Field(default_factory=list)


class AIGeneratedQuestion(BaseModel):
    question_text: str
    question_type: str = "multiple_choice"  # multiple_choice, short_answer, numerical
    options: List[str] = Field(default_factory=list)
    correct_answer: str
    worked_explanation: str
    difficulty_level: str = "medium"  # easy, medium, hard
    learning_objective: Optional[str] = None
    source_page_reference: Optional[str] = None


class AnswerEvaluation(BaseModel):
    is_correct: bool
    score: float
    max_marks: float = 1.0
    feedback: str
    pedagogical_guidance: str
    step_by_step_correction: Optional[str] = None


class GeminiService:
    """
    Dedicated service for textbook-grounded tutoring and question generation
    using the official Google GenAI Python SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if not self.api_key or self.api_key.strip() in ("", "your_gemini_api_key_here"):
            raise GeminiAuthError("Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env")

        if self._client is None:
            try:
                self._client = genai.Client(
                    api_key=self.api_key,
                    http_options={"api_version": "v1beta"},
                )
            except Exception as e:
                raise GeminiAuthError(f"Failed to initialize Gemini client: {str(e)}")
        return self._client

    def _parse_client_error(self, e: Exception) -> Exception:
        """
        Parses Google GenAI client errors, sanitizing sensitive keys and classifying
        temporary request rate limits vs daily/project quota exhaustion.
        """
        import re
        err_str = str(e)
        if self.api_key:
            err_str = err_str.replace(self.api_key, "[REDACTED_API_KEY]")

        if "401" in err_str or "API_KEY_INVALID" in err_str:
            return GeminiAuthError("Gemini API key is invalid or unauthorized. Please verify GEMINI_API_KEY.")

        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            retry_seconds = None
            match_sec = re.search(r"retry\s*(?:after|in)?\s*(\d+)\s*s", err_str, re.IGNORECASE)
            if match_sec:
                try:
                    retry_seconds = int(match_sec.group(1))
                except ValueError:
                    pass

            is_daily = any(w in err_str.lower() for w in ["per day", "free tier limit", "daily quota", "quota metric"])

            if is_daily:
                msg = (
                    "The daily or free-tier Gemini API quota for this project has been exhausted. "
                    "The application must wait for the daily quota reset before making new AI requests. "
                    "Note: If project quota is exhausted, switching models will not necessarily solve the issue."
                )
            elif retry_seconds:
                msg = (
                    f"Gemini API rate limit reached. Provider advises waiting {retry_seconds} seconds before retrying."
                )
            else:
                msg = (
                    "Gemini API rate limit or resource quota reached. "
                    "Please wait a moment before sending another request, or wait for your daily quota to reset."
                )

            return GeminiQuotaError(
                message=msg,
                retry_after_seconds=retry_seconds,
                is_daily_exhaustion=is_daily,
            )

        if "404" in err_str or "NOT_FOUND" in err_str:
            return GeminiError(
                f"Configured model '{self.model}' is not available for this project. Please select a supported model (e.g. gemini-3.5-flash)."
            )

        return GeminiError(f"Gemini API error: {err_str}")

    def _generate_content(self, contents: Any, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes generate_content on the configured model without uncontrolled retry loops.
        Respects provider guidance and handles temporary 503 unavailability with a single brief pause.
        """
        import time
        client = self._get_client()

        try:
            return client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except genai_errors.ClientError as e:
            raise self._parse_client_error(e)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(1.0)
                try:
                    return client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                except Exception as retry_e:
                    raise self._parse_client_error(retry_e)
            raise self._parse_client_error(e)

    def is_available(self) -> Tuple[bool, str]:
        """Check if Gemini service is configured and operational."""
        if not self.api_key or self.api_key.strip() in ("", "your_gemini_api_key_here"):
            return False, "GEMINI_API_KEY is not configured in backend/.env"
        try:
            client = self._get_client()
            res = client.models.generate_content(
                model=self.model,
                contents="ping",
            )
            if res and res.text:
                return True, f"Operational (Model: {self.model})"
            return False, "Model returned empty response"
        except genai_errors.ClientError as e:
            if "401" in str(e) or "API_KEY_INVALID" in str(e):
                return False, "Invalid API key"
            if "429" in str(e):
                return False, "Quota exceeded"
            return False, f"Client error: {str(e)}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def ask_tutor(
        self,
        query: str,
        retrieved_passages: List[Dict[str, Any]],
        grade: int,
        subject: str,
        language: str = "English",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> TutorExplanation:
        """
        Generates a pedagogical, grounded response using retrieved textbook passages.
        Adheres to strict truthfulness: if sources are insufficient, clearly flags it.
        """
        client = self._get_client()

        # Build context from passages
        passage_context_blocks = []
        citations: List[CitationRef] = []

        for idx, p in enumerate(retrieved_passages, 1):
            doc_title = p.get("source_title", "Official Textbook")
            page_num = p.get("page_number", 1)
            heading = p.get("heading", "")
            content = p.get("content", "").strip()

            passage_context_blocks.append(
                f"[Source {idx}] (Title: {doc_title}, Page: {page_num}, Section: {heading})\n{content}"
            )
            citations.append(
                CitationRef(
                    source_title=doc_title,
                    page_number=page_num,
                    heading=heading,
                    excerpt=content[:150] + "..." if len(content) > 150 else content,
                )
            )

        context_text = "\n\n".join(passage_context_blocks) if passage_context_blocks else "NO_RELEVANT_TEXTBOOK_PASSAGES_FOUND"

        system_instruction = f"""You are the VidyaFlow AI Learning Coach, an encouraging tutor for school students in Class {grade} studying {subject}.
Language of reply: {language}.

Your pedagogical guidelines:
1. GROUNDING IN TEXTBOOK: Use the provided textbook passages as your primary source of truth.
2. If the provided textbook passages are insufficient to answer the student's question accurately, explicitly state:
   "The available textbook material does not have sufficient information on this specific question." Do NOT fabricate citations or textbook page numbers.
3. CLASS-APPROPRIATE: Explain clearly at a Class {grade} conceptual level without unnecessary jargon.
4. HINTS BEFORE SOLUTIONS: If the student asks how to solve a problem, provide progressive hints and the underlying principle first.
5. STEP-BY-STEP: Give clear, numbered steps for mathematical or scientific derivations.

Respond STRICTLY in JSON format matching this schema:
{{
  "explanation": "Clear, friendly explanation formatted in markdown",
  "key_points": ["Key concept 1", "Key concept 2"],
  "hints": ["Helpful hint if student is practicing", "Guiding question"],
  "is_textbook_grounded": true or false,
  "grounding_notes": "Note on which textbook section supported this"
}}
"""

        prompt = f"""TEXTBOOK CONTEXT:
{context_text}

STUDENT QUESTION:
{query}
"""
        # Append conversation context if provided
        if history:
            history_text = "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in history[-4:]])
            prompt = f"PREVIOUS CONVERSATION:\n{history_text}\n\n{prompt}"

        try:
            response = self._generate_content(
                contents=prompt,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                },
            )

            raw_text = response.text.strip()
            data = json.loads(raw_text)

            return TutorExplanation(
                explanation=data.get("explanation", ""),
                key_points=data.get("key_points", []),
                hints=data.get("hints", []),
                is_textbook_grounded=data.get("is_textbook_grounded", bool(retrieved_passages)),
                grounding_notes=data.get("grounding_notes", ""),
                citations=citations if data.get("is_textbook_grounded", True) else [],
            )

        except genai_errors.ClientError as e:
            if "401" in str(e) or "API_KEY_INVALID" in str(e):
                raise GeminiAuthError()
            if "429" in str(e):
                raise GeminiQuotaError()
            raise GeminiError(f"Gemini API error: {str(e)}")
        except json.JSONDecodeError as e:
            raise GeminiResponseError(f"Model did not return valid JSON: {str(e)}")
        except Exception as e:
            raise GeminiError(f"Tutor request failed: {str(e)}")

    def generate_questions(
        self,
        passages: List[Dict[str, Any]],
        count: int = 3,
        difficulty: str = "medium",
        grade: int = 10,
        subject: str = "Mathematics",
        chapter_title: str = "Core Concepts",
    ) -> List[AIGeneratedQuestion]:
        """
        Generates original practice questions strictly aligned with curriculum passages.
        Validates MCQ answer keys and options.
        """
        client = self._get_client()

        context_texts = [f"[Page {p.get('page_number', 1)}: {p.get('heading', '')}]\n{p.get('content', '')}" for p in passages]
        full_context = "\n\n".join(context_texts) if context_texts else f"Curriculum topic: {chapter_title} for Class {grade} {subject}."

        system_instruction = f"""You are a specialized curriculum assessment designer for Class {grade} {subject} ({chapter_title}).
Create {count} ORIGINAL practice questions grounded in the provided textbook passages.

Rules:
1. Do not reproduce copyrighted textbook questions verbatim. Create original questions testing the same concepts.
2. Difficulty target: {difficulty} (easy, medium, hard).
3. For multiple-choice questions, provide exactly 4 options. Exactly ONE option must be mathematically/conceptually correct.
4. For 'correct_answer', provide the exact matching string of the correct option.
5. Provide a clear, worked explanation justifying the answer.
6. Record the page reference from the context that supported the question.

Respond STRICTLY in JSON with a list of questions:
[
  {{
    "question_text": "Question text here",
    "question_type": "multiple_choice",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option B",
    "worked_explanation": "Step-by-step solution",
    "difficulty_level": "{difficulty}",
    "source_page_reference": "Page X"
  }}
]
"""

        try:
            response = self._generate_content(
                contents=f"CURRICULUM TEXTBOOK PASSAGES:\n{full_context}\n\nGenerate {count} questions.",
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                },
            )

            raw_text = response.text.strip()
            data = json.loads(raw_text)
            if not isinstance(data, list):
                if isinstance(data, dict) and "questions" in data:
                    data = data["questions"]
                else:
                    data = [data]

            validated_questions = []
            for item in data:
                # Validate MCQ has options and correct_answer matches an option
                opts = item.get("options", [])
                ans = str(item.get("correct_answer", ""))
                if item.get("question_type") == "multiple_choice" and len(opts) >= 2:
                    # Ensure correct_answer is in options
                    if ans not in opts and ans.isdigit() and int(ans) < len(opts):
                        ans = opts[int(ans)]

                validated_questions.append(
                    AIGeneratedQuestion(
                        question_text=item["question_text"],
                        question_type=item.get("question_type", "multiple_choice"),
                        options=opts,
                        correct_answer=ans,
                        worked_explanation=item.get("worked_explanation", "Standard solution."),
                        difficulty_level=item.get("difficulty_level", difficulty),
                        source_page_reference=item.get("source_page_reference"),
                    )
                )

            return validated_questions

        except genai_errors.ClientError as e:
            if "401" in str(e) or "API_KEY_INVALID" in str(e):
                raise GeminiAuthError()
            if "429" in str(e):
                raise GeminiQuotaError()
            raise GeminiError(f"Gemini API error: {str(e)}")
        except Exception as e:
            raise GeminiError(f"Question generation failed: {str(e)}")

    def evaluate_subjective_answer(
        self,
        question_text: str,
        student_answer: str,
        worked_explanation: str,
        correct_answer: str,
        marks: float = 1.0,
    ) -> AnswerEvaluation:
        """
        Evaluates a subjective or short-answer response against the rubric using Gemini.
        """
        client = self._get_client()

        prompt = f"""QUESTION:
{question_text}

IDEAL / CORRECT ANSWER:
{correct_answer}

WORKED EXPLANATION / RUBRIC:
{worked_explanation}

STUDENT SUBMITTED ANSWER:
{student_answer}

MAXIMUM MARKS:
{marks}

Evaluate the student's answer fairly and constructively.
Return JSON format:
{{
  "is_correct": true if student showed conceptual mastery else false,
  "score": float between 0.0 and {marks},
  "max_marks": {marks},
  "feedback": "Encouraging, direct feedback",
  "pedagogical_guidance": "What the student should focus on to improve",
  "step_by_step_correction": "Corrected step if partial credit was given"
}}
"""

        try:
            response = self._generate_content(
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            data = json.loads(response.text.strip())
            return AnswerEvaluation(
                is_correct=bool(data.get("is_correct", False)),
                score=float(data.get("score", 0.0)),
                max_marks=marks,
                feedback=data.get("feedback", "Answer reviewed."),
                pedagogical_guidance=data.get("pedagogical_guidance", "Keep practicing core concepts."),
                step_by_step_correction=data.get("step_by_step_correction"),
            )

        except Exception as e:
            logger.warning(f"AI evaluation fallback due to: {e}")
            # Fallback simple evaluation if Gemini fails
            is_match = student_answer.strip().lower() == correct_answer.strip().lower()
            return AnswerEvaluation(
                is_correct=is_match,
                score=marks if is_match else 0.0,
                max_marks=marks,
                feedback="Exact match check (AI evaluation service temporarily unavailable)." if not is_match else "Correct!",
                pedagogical_guidance="Review the worked explanation.",
            )
