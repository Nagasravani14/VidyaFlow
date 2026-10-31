"""
VidyaFlow - Dual LLM Service (Google Gemini & Groq Free Tier)
Provides zero-cost, high-reliability LLM generation for:
- Student Interactive Quiz generation
- Teacher Worksheet & Answer Key generation
- Syllabus Doubt Resolver chatbot
- Instant answer evaluation
With automatic failover between Gemini and Groq, plus offline fallback generation.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("vidyaflow.llm_engine")


def extract_json_from_text(text: str) -> Any:
    """
    Safely extracts and parses JSON from LLM outputs, stripping Markdown code fences,
    handling trailing commas, and repairing partial JSON structures.
    """
    if not text:
        raise ValueError("Empty response text from LLM")

    # Clean zero-width chars and whitespace
    text = text.replace("\ufeff", "").strip()

    # Pattern 1: fenced code block ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # Pattern 2: direct JSON search from first { or [ to last } or ]
    first_bracket = min([pos for pos in (text.find("{"), text.find("[")) if pos != -1], default=-1)
    last_bracket = max(text.rfind("}"), text.rfind("]"))

    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket : last_bracket + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Attempt to fix trailing commas before } or ]
            cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

    # Pattern 3: Clean trailing commas on the full string
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned_full = re.sub(r",\s*([\]}])", r"\1", text)
        try:
            return json.loads(cleaned_full)
        except json.JSONDecodeError:
            pass

    # Pattern 4: Python ast evaluation for single-quoted dicts/lists
    try:
        import ast
        val = ast.literal_eval(text)
        if isinstance(val, (dict, list)):
            return val
    except Exception:
        pass

    raise ValueError(f"Could not extract valid JSON from LLM response (length {len(text)})")


VIDYAFLOW_ADAPTIVE_QUIZ_MASTER_SYSTEM_PROMPT = """================================================================================
VIDYAFLOW ADAPTIVE QUIZ & ASSESSMENT ENGINE - MASTER SYSTEM PROMPT
================================================================================

[ROLE & PERSONA]
You are VidyaFlow's Principal AI Pedagogy Specialist and Assessment Designer, specialized in K-10 curriculum design (Telangana SCERT, NCERT, and ICSE). Your task is to generate rigorous, diverse, age-appropriate, and non-repetitive quiz questions derived STRICTLY from provided textbook context. You NEVER invent facts, hallucinate chapters, or reuse repetitive question templates.

[CORE OBJECTIVES]
1. GENERATE HIGH-DIVERSITY QUESTIONS: Vary syntax, context, cognitive depth, and question formats (MCQ, Fill in the Blanks, Short Conceptual Checks).
2. STICK TO TEXTBOOK CONTEXT: Ground every question directly in the retrieved RAG textbook passages provided.
3. IDENTIFY ROOT KNOWLEDGE GAPS: Tag each question with its exact prerequisite concept so that if a student fails, VidyaFlow can pinpoint the underlying weakness.
4. STRICT STRUCTURED OUTPUT: Return ONLY valid JSON adhering strictly to the required schema.

--------------------------------------------------------------------------------
[INPUT PARAMETERS PROVIDED AT RUNTIME]
- BOARD & CLASS: {board_name} | Class {class_level}
- SUBJECT & CHAPTER: {subject_name} | Chapter: {chapter_name}
- TARGET CONCEPT: {concept_name}
- CONCEPT PREREQUISITES: {prerequisite_list}
- DIFFICULTY LEVEL: {target_difficulty}  # "easy" | "medium" | "hard"
- QUESTION COUNT: {num_questions}
- DIVERSITY SEED/FOCUS: {focus_skills}   # e.g., ["definition", "numerical-problem", "real-world application", "misconception-check"]

[RETIREVED TEXTBOOK CONTEXT (RAG PASSAGES)]
--------------------------------------------------------------------------------
{retrieved_rag_chunks}
--------------------------------------------------------------------------------

[GENERATION RULES & CONSTRAINTS]

1. QUESTION FORMAT DIVERSITY (Strict Proportions):
   - 40% Conceptual Understanding (Multiple Choice Questions)
   - 30% Application / Problem-Solving / Real-world Scenarios
   - 30% Analytical / Fill-in-the-Blank / True-False with Reasoning

2. DIFFICULTY ADJUSTMENT RULES:
   - EASY: Direct recall, simple definitions, basic visual or single-step understanding.
   - MEDIUM: Multi-step thinking, applying rules to simple word problems, identifying correct relationships.
   - HARD: Critical analysis, multi-concept synthesis, edge-case scenarios, spot-the-mistake questions.

3. ANTI-REPETITION MANDATE:
   - DO NOT start consecutive questions with the same phrase (e.g., "Which of the following...", "What is...").
   - Randomize option order and ensure correct answer distribution (A, B, C, D are evenly balanced).
   - Distractors (incorrect options) MUST represent common student misconceptions, NOT random or silly answers.

4. HINT & EXPLANATION DESIGN:
   - Hints must NOT give away the answer. Hints should prompt critical thinking or point to a foundational principle.
   - Explanations must be step-by-step, simple, encouraging, and cite textbook logic directly.

--------------------------------------------------------------------------------
[OUTPUT FORMAT REQUIREMENT]
Return the complete result as a single, valid JSON object following this EXACT schema (No markdown commentary around the raw JSON block):

{{
  "concept_id": "{concept_name}",
  "difficulty_level": "{target_difficulty}",
  "total_questions": {num_questions},
  "questions": [
    {{
      "question_id": "q1",
      "question_type": "mcq",
      "cognitive_level": "application",
      "difficulty": "{target_difficulty}",
      "question_text": "Clear, engaging question statement grounded strictly in textbook context...",
      "options": [
        {{"option_id": "A", "text": "Option A text"}},
        {{"option_id": "B", "text": "Option B text"}},
        {{"option_id": "C", "text": "Option C text"}},
        {{"option_id": "D", "text": "Option D text"}}
      ],
      "correct_answer": "B",
      "hint": "Guiding clue that encourages thinking without revealing the solution...",
      "explanation": "Clear, step-by-step conceptual breakdown of why B is correct...",
      "prerequisite_concept_tested": "The underlying foundational topic (e.g., Variables, Simplification)",
      "root_gap_remediation": "If the student gets this wrong, review this specific prerequisite topic before attempting again."
    }}
  ]
}}
"""


class LLMEngine:
    """
    Orchestrates LLM requests with primary Google Gemini and fallback Groq,
    ensuring robust textbook-grounded responses.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        groq_model: Optional[str] = None,
    ):
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")

        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.groq_model = groq_model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        # Lazy clients
        self._gemini_client = None
        self._groq_client = None

    def _get_gemini_client(self):
        if self._gemini_client is None and self.gemini_api_key:
            try:
                # Try new google-genai SDK first
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize google.genai Client: {e}")
        return self._gemini_client

    def _get_groq_client(self):
        if self._groq_client is None and self.groq_api_key:
            try:
                import groq
                self._groq_client = groq.Groq(api_key=self.groq_api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}")
        return self._groq_client

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> Tuple[str, str]:
        """
        Executes text generation trying Gemini first, then Groq.
        Returns (response_text, provider_name).
        """
        last_error = None

        # 1. Try Google Gemini
        if self.gemini_api_key:
            client = self._get_gemini_client()
            if client:
                candidate_models = [self.gemini_model, "gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
                for model in dict.fromkeys(candidate_models):
                    try:
                        config = {}
                        if system_instruction:
                            config["system_instruction"] = system_instruction
                        response = client.models.generate_content(
                            model=model,
                            contents=prompt,
                            config=config if config else None,
                        )
                        if response and response.text:
                            return response.text, f"gemini:{model}"
                    except Exception as e:
                        last_error = e
                        logger.warning(f"Gemini model {model} attempt failed: {e}")

        # 2. Try Groq (Free Tier API)
        if self.groq_api_key:
            groq_client = self._get_groq_client()
            if groq_client:
                candidate_models = [self.groq_model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
                for model in dict.fromkeys(candidate_models):
                    try:
                        messages = []
                        if system_instruction:
                            messages.append({"role": "system", "content": system_instruction})
                        messages.append({"role": "user", "content": prompt})

                        resp = groq_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=0.3,
                        )
                        if resp.choices and resp.choices[0].message.content:
                            return resp.choices[0].message.content, f"groq:{model}"
                    except Exception as e:
                        last_error = e
                        logger.warning(f"Groq model {model} attempt failed: {e}")

        logger.error(f"All LLM providers failed or unconfigured. Last error: {last_error}")
        return "", "offline_fallback"

    # =========================================================================
    # A) STUDENT QUIZ ENGINE
    # =========================================================================
    def generate_quiz(
        self,
        board: str,
        class_num: int,
        subject: str,
        chapter: str,
        count: int = 10,
        context_chunks: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates 10 to 20 structured MCQs with options, correct answer index, and step-by-step solutions.
        Guaranteed zero HTTP failure: fallbacks gracefully complete the question set.
        """
        # Clamp count to between 1 and 20
        count = max(1, min(20, count))
        context_str = "\n\n---\n\n".join(context_chunks or [])
        if not context_str.strip():
            context_str = f"Syllabus Topic: {board} Board, Class {class_num}, Subject: {subject}, Chapter: {chapter}."

        prompt = f"""You are a master curriculum examiner for {board} Board (Class {class_num}).
Generate exactly {count} distinct, comprehensive Multiple Choice Questions (MCQs) for:
Subject: {subject}
Chapter: {chapter}

Use the following official textbook context snippets:
{context_str}

STRICT JSON OUTPUT REQUIREMENT:
Return ONLY a valid JSON array of {count} objects. Do not include markdown code fences or conversational text.
Format each question strictly as:
[
  {{
    "id": "q1",
    "question": "Clear, precise question text covering definitions, laws, calculations, or applications?",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "correct_option_index": 0,
    "correct_option": "A) Option 1",
    "solution": "Step-by-step pedagogical explanation of why this answer is correct."
  }}
]
"""
        system_instruction = (
            f"You are a Senior Academic Specialist for {board} Board Class {class_num} {subject}. "
            f"Always ground your questions in verified curriculum standards and return strict JSON."
        )

        cleaned_questions: List[Dict[str, Any]] = []

        try:
            response_text, provider = self.generate_text(prompt, system_instruction=system_instruction)
            if response_text:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict) and "questions" in data:
                    data = data["questions"]
                if isinstance(data, list) and len(data) > 0:
                    for idx, item in enumerate(data, 1):
                        opts = item.get("options", [])
                        if not isinstance(opts, list) or len(opts) < 4:
                            opts = [str(o) for o in (opts if isinstance(opts, list) else [])]
                            while len(opts) < 4:
                                opts.append(f"Option {chr(65 + len(opts))}")
                        c_idx = item.get("correct_option_index", 0)
                        if not isinstance(c_idx, int) or c_idx < 0 or c_idx >= len(opts):
                            c_idx = 0
                        c_opt = str(item.get("correct_option", opts[c_idx]))

                        cleaned_questions.append({
                            "id": str(item.get("id", f"q_{idx}")),
                            "question": str(item.get("question", f"Question {idx} on {chapter}")),
                            "options": [str(o) for o in opts[:4]],
                            "correct_option_index": c_idx,
                            "correct_option": c_opt,
                            "solution": str(item.get("solution", f"Based on {board} Class {class_num} textbook concepts for {chapter}.")),
                        })
        except Exception as e:
            logger.warning(f"Failed to generate LLM quiz: {e}. Supplementing with deterministic curriculum bank.")

        # If LLM returned enough questions, return top count
        if len(cleaned_questions) >= count:
            return cleaned_questions[:count]

        # Otherwise fill remainder from the deterministic curriculum generator
        needed = count - len(cleaned_questions)
        supplement = self._fallback_quiz_generator(board, class_num, subject, chapter, needed, context_chunks)
        # Shift IDs to prevent duplicate IDs
        start_id = len(cleaned_questions) + 1
        for idx, item in enumerate(supplement):
            item["id"] = f"q_{start_id + idx}"
            cleaned_questions.append(item)

        return cleaned_questions[:count]

    def _fallback_quiz_generator(
        self, board: str, class_num: int, subject: str, chapter: str, count: int, context_chunks: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Deterministic, curriculum-aligned question generator with complete coverage
        across 238 chapters in TS and ICSE (Classes 6-10). Produces up to 20 unique MCQs.
        """
        ch_lower = chapter.lower()
        sub_lower = subject.lower()

        # Subject-specific rich banks
        is_math = "math" in sub_lower or "algebra" in ch_lower or "number" in ch_lower or "geometry" in ch_lower or "mensuration" in ch_lower
        is_physics = "physic" in sub_lower or "light" in ch_lower or "motion" in ch_lower or "force" in ch_lower or "electr" in ch_lower or "magnet" in ch_lower or "sound" in ch_lower
        is_bio = "bio" in sub_lower or "cell" in ch_lower or "plant" in ch_lower or "food" in ch_lower or "life" in ch_lower or "tissue" in ch_lower or "nutrition" in ch_lower
        is_social = "social" in sub_lower or "history" in ch_lower or "geograph" in ch_lower or "constitut" in ch_lower or "earth" in ch_lower or "relief" in ch_lower

        templates: List[Dict[str, Any]] = []

        if is_physics:
            templates = [
                {
                    "q": f"What is the fundamental SI unit of measurement associated with {chapter}?",
                    "opts": ["Joule (J)", "Newton (N)", "Standard SI derived unit", "Watt (W)"],
                    "ans": 2,
                    "sol": f"In {board} Class {class_num} {subject}, quantities in {chapter} are measured in standard SI coherent units.",
                },
                {
                    "q": f"Which fundamental physical law governs phenomena observed in {chapter}?",
                    "opts": ["Law of Conservation of Energy", "Law of Linear Invariance", "Kepler's Second Approximation", "Newton's Universal Expansion"],
                    "ans": 0,
                    "sol": "Energy and momentum conservation are universal axioms underpinning physical interactions.",
                },
                {
                    "q": f"When light passes from an optically denser medium to a rarer medium in {chapter}, what happens to its speed and direction?",
                    "opts": ["Speed decreases, bends towards normal", "Speed increases, bends away from normal", "Speed remains constant, no deviation", "Speed decreases, undergoes total reflection"],
                    "ans": 1,
                    "sol": "In an optically rarer medium, light travels faster, causing the wave front to bend away from the normal according to Snell's Law.",
                },
                {
                    "q": f"What is the condition for Total Internal Reflection to occur in {chapter}?",
                    "opts": ["Light travels from rarer to denser medium with i < C", "Light travels from denser to rarer medium with i > C", "Angle of incidence equals zero", "Medium must have refractive index equal to 1.0"],
                    "ans": 1,
                    "sol": "Total internal reflection requires light to travel from a denser into a rarer medium with an incident angle greater than the critical angle C.",
                },
                {
                    "q": f"For a spherical mirror or lens in {chapter}, the relationship between focal length (f) and radius of curvature (R) is:",
                    "opts": ["f = 2R", "f = R / 2", "f = R²", "f = 1 / R"],
                    "ans": 1,
                    "sol": "For mirrors and lenses with small apertures, the principal focus lies halfway between the pole and center of curvature: f = R / 2.",
                },
                {
                    "q": f"Which factor directly affects the magnitude of force or field strength in {chapter}?",
                    "opts": ["Inverse square of the distance", "Linear ratio of ambient temperature", "Barometric pressure exclusively", "Color of the interacting bodies"],
                    "ans": 0,
                    "sol": "Inverse square laws govern electrostatic, gravitational, and magnetic field strengths across physical models.",
                },
                {
                    "q": f"What is the power of a lens with focal length of +0.5 meters?",
                    "opts": ["+0.5 D", "+1.0 D", "+2.0 D", "-2.0 D"],
                    "ans": 2,
                    "sol": "Power P = 1 / f(in metres). For f = +0.5 m, P = 1 / 0.5 = +2.0 Dioptres (converging).",
                },
                {
                    "q": f"According to Ohm's Law or dynamic equilibrium in {chapter}, current is directly proportional to:",
                    "opts": ["Resistance", "Potential difference (Voltage)", "Temperature", "Length of wire squared"],
                    "ans": 1,
                    "sol": "At constant physical conditions, current (I) is directly proportional to applied potential difference (V): V = IR.",
                },
                {
                    "q": f"What type of image is formed on a screen by a converging system when the object is beyond 2F?",
                    "opts": ["Virtual, erect, enlarged", "Real, inverted, diminished", "Virtual, inverted, same size", "Real, erect, diminished"],
                    "ans": 1,
                    "sol": "An object placed beyond 2F of a converging convex lens forms a real, inverted, and diminished image between F and 2F.",
                },
                {
                    "q": f"In experimental investigations for {chapter}, systematic errors can be minimized by:",
                    "opts": ["Ignoring calibration offsets", "Taking repeated measurements and averaging", "Using arbitrary non-standard scales", "Changing environmental variables mid-test"],
                    "ans": 1,
                    "sol": "Multiple trials and calculating the arithmetic mean cancels out random observation errors.",
                },
            ]
        elif is_math:
            templates = [
                {
                    "q": f"What is the degree of the polynomial expression associated with {chapter} in standard form?",
                    "opts": ["Highest exponent of the variable", "Sum of all coefficients", "Number of terms in the polynomial", "Constant term value"],
                    "ans": 0,
                    "sol": "The degree of a polynomial in a single variable is defined as the greatest power of the variable present with a non-zero coefficient.",
                },
                {
                    "q": f"Which algebraic identity correctly expresses (a + b)(a - b) in {chapter}?",
                    "opts": ["a² + b²", "a² - b²", "a² - 2ab + b²", "a² + 2ab + b²"],
                    "ans": 1,
                    "sol": "The product of the sum and difference of two terms is the difference of their squares: (a + b)(a - b) = a² - b².",
                },
                {
                    "q": f"What is the solution of the linear equation 4x - 8 = 16 in {chapter}?",
                    "opts": ["x = 2", "x = 4", "x = 6", "x = 8"],
                    "ans": 2,
                    "sol": "Adding 8 to both sides: 4x = 24. Dividing both sides by 4: x = 6.",
                },
                {
                    "q": f"If two quantities x and y are in direct proportion, which relation holds constant?",
                    "opts": ["x * y = k", "x / y = k", "x + y = k", "x - y = k"],
                    "ans": 1,
                    "sol": "Direct variation means the ratio of corresponding values of x and y remains constant: x / y = k.",
                },
                {
                    "q": f"What is the total surface area of a cube having side length 'a' in {chapter}?",
                    "opts": ["4a²", "6a²", "a³", "12a"],
                    "ans": 1,
                    "sol": "A cube consists of 6 identical square faces, each of area a², so Total Surface Area = 6a².",
                },
                {
                    "q": f"The discriminant (D = b² - 4ac) determines nature of roots. If D > 0 and a perfect square, roots are:",
                    "opts": ["Real, rational, and unequal", "Real and equal", "Imaginary / complex", "Undetermined"],
                    "ans": 0,
                    "sol": "When the discriminant D > 0 and is a perfect square, the quadratic equation possesses two distinct rational roots.",
                },
                {
                    "q": f"Factorise completely: 9x² - 25y².",
                    "opts": ["(3x - 5y)²", "(3x + 5y)(3x - 5y)", "(9x - 25y)(x + y)", "3x(3x - 5y)"],
                    "ans": 1,
                    "sol": "Using difference of squares a² - b² = (a + b)(a - b), where a = 3x and b = 5y: (3x + 5y)(3x - 5y).",
                },
                {
                    "q": f"In a right-angled triangle, if perpendicular is 3 cm and base is 4 cm, the hypotenuse is:",
                    "opts": ["5 cm", "7 cm", "6 cm", "12 cm"],
                    "ans": 0,
                    "sol": "By Pythagoras theorem: Hypotenuse = √(3² + 4²) = √(9 + 16) = √25 = 5 cm.",
                },
                {
                    "q": f"The median of the sorted data set [2, 5, 7, 10, 14, 18, 21] is:",
                    "opts": ["7", "10", "12", "14"],
                    "ans": 1,
                    "sol": "With n = 7 (odd), the median is the (7 + 1)/2 = 4th observation, which is 10.",
                },
                {
                    "q": f"Which value of x satisfies the identity (x + 3)² = x² + 6x + 9?",
                    "opts": ["Only x = 0", "Only positive integers", "All real values of x", "Only x = 3"],
                    "ans": 2,
                    "sol": "An algebraic identity is an equality that is valid for all values of the variables involved.",
                },
            ]
        elif is_bio:
            templates = [
                {
                    "q": f"What is the basic structural and functional unit of life discussed in {chapter}?",
                    "opts": ["Tissue", "Organ", "Cell", "Organelle"],
                    "ans": 2,
                    "sol": "The cell is the fundamental structural, functional, and biological unit of all known organisms.",
                },
                {
                    "q": f"Which cellular organelle is known as the 'powerhouse of the cell'?",
                    "opts": ["Ribosome", "Golgi apparatus", "Mitochondria", "Endoplasmic Reticulum"],
                    "ans": 2,
                    "sol": "Mitochondria generate most of the chemical energy needed to power the cell's biochemical reactions in the form of ATP.",
                },
                {
                    "q": f"During photosynthesis in green plants, light energy is absorbed primarily by:",
                    "opts": ["Chlorophyll", "Carotenoids", "Mitochondria", "Stomata pores"],
                    "ans": 0,
                    "sol": "Chlorophyll pigment inside chloroplast thylakoids absorbs photons of light to drive the light reactions of photosynthesis.",
                },
                {
                    "q": f"Which vascular tissue is responsible for transporting water and minerals from roots to leaves?",
                    "opts": ["Phloem", "Xylem", "Cambium", "Parenchyma"],
                    "ans": 1,
                    "sol": "Xylem conducts water and dissolved mineral nutrients unidirectionally from roots throughout the plant body.",
                },
                {
                    "q": f"What is the end product of aerobic respiration in eukaryotic cells?",
                    "opts": ["Lactic acid and energy", "Ethanol and CO2", "Carbon dioxide, water, and ATP energy", "Glucose and oxygen"],
                    "ans": 2,
                    "sol": "Aerobic respiration completely oxidizes glucose in the presence of O2 to yield CO2, H2O, and 36-38 ATP molecules.",
                },
                {
                    "q": f"Which gland is referred to as the master endocrine gland in human physiology?",
                    "opts": ["Thyroid gland", "Pituitary gland", "Adrenal gland", "Pancreas"],
                    "ans": 1,
                    "sol": "The pituitary gland secretes tropic hormones that regulate other endocrine glands throughout the body.",
                },
                {
                    "q": f"In genetics, the physical or observable expression of a gene combination is called:",
                    "opts": ["Genotype", "Phenotype", "Allele", "Heterozygous"],
                    "ans": 1,
                    "sol": "Phenotype represents the observable physical, physiological, or biochemical traits of an organism determined by its genotype.",
                },
                {
                    "q": f"Which blood cells play the primary role in defense and producing antibodies against pathogens?",
                    "opts": ["Erythrocytes (RBCs)", "Leukocytes (WBCs)", "Thrombocytes (Platelets)", "Blood Plasma"],
                    "ans": 1,
                    "sol": "White blood cells (lymphocytes and phagocytes) defend the body against foreign infectious agents and disease.",
                },
                {
                    "q": f"What is the primary function of stomata in plant leaves?",
                    "opts": ["Absorption of soil water", "Gas exchange and transpiration", "Protection against insects", "Anchoring the leaf"],
                    "ans": 1,
                    "sol": "Stomata allow the diffusion of carbon dioxide and oxygen for photosynthesis and respiration, and facilitate transpiration.",
                },
                {
                    "q": f"Which enzyme initiates carbohydrate breakdown in the human digestive system?",
                    "opts": ["Pepsin", "Salivary Amylase (Ptyalin)", "Lipase", "Trypsin"],
                    "ans": 1,
                    "sol": "Salivary amylase hydrolyzes dietary starch into simpler maltose disaccharides in the mouth.",
                },
            ]
        else: # Social Studies or general curriculum
            templates = [
                {
                    "q": f"What is the primary objective of studying {chapter} in {board} Class {class_num} Social Studies?",
                    "opts": ["To understand socio-economic, constitutional, and geographical frameworks", "To memorize arbitrary chronological lists", "To study pure laboratory procedures", "To analyze abstract calculus"],
                    "ans": 0,
                    "sol": f"Social Studies curriculum for Class {class_num} builds active democratic citizenship, historical understanding, and spatial geographical analysis.",
                },
                {
                    "q": f"Who is recognized as the chief architect of the Indian Constitution?",
                    "opts": ["Mahatma Gandhi", "Dr. B. R. Ambedkar", "Jawaharlal Nehru", "Sardar Vallabhbhai Patel"],
                    "ans": 1,
                    "sol": "Dr. B.R. Ambedkar served as the Chairman of the Drafting Committee of the Constituent Assembly.",
                },
                {
                    "q": f"Which latitude divides India into almost two equal halves?",
                    "opts": ["Equator (0°)", "Tropic of Cancer (23° 30' N)", "Tropic of Capricorn (23° 30' S)", "Standard Meridian (82° 30' E)"],
                    "ans": 1,
                    "sol": "The Tropic of Cancer passes through 8 Indian states, dividing the subcontinent into northern sub-tropical and southern tropical zones.",
                },
                {
                    "q": f"In a parliamentary democracy, the executive branch is accountable to:",
                    "opts": ["The Judiciary", "The Legislature (Parliament)", "The Bureaucracy", "The Armed Forces"],
                    "ans": 1,
                    "sol": "The Council of Ministers headed by the Prime Minister is collectively responsible to the Lok Sabha (House of the People).",
                },
                {
                    "q": f"What is the primary sector of an economy predominantly comprised of?",
                    "opts": ["Manufacturing and processing", "Agriculture, forestry, and mining", "Banking and IT services", "International shipping"],
                    "ans": 1,
                    "sol": "The primary sector exploits natural resources directly, including agriculture, dairy, fishing, and forestry.",
                },
                {
                    "q": f"Which river system is known as the 'Dakshin Ganga' or the largest peninsular river of India?",
                    "opts": ["Krishna", "Godavari", "Cauvery", "Mahanadi"],
                    "ans": 1,
                    "sol": "The Godavari originates in Trimbakeshwar (Nashik, Maharashtra) and is the largest peninsular river in India.",
                },
                {
                    "q": f"What is the minimum voting age for an Indian citizen under Universal Adult Suffrage?",
                    "opts": ["16 years", "18 years", "21 years", "25 years"],
                    "ans": 1,
                    "sol": "The 61st Constitutional Amendment Act, 1988 reduced the voting age for Lok Sabha and Assembly elections from 21 to 18 years.",
                },
                {
                    "q": f"Which factor is most significant in determining the climate of the Indian subcontinent?",
                    "opts": ["Monsoon wind circulation", "Longitude coordinates", "Tectonic plate thickness", "Desert soil salinity"],
                    "ans": 0,
                    "sol": "The southwest and northeast monsoon winds dictate the seasonal rainfall and climatic patterns of the subcontinent.",
                },
                {
                    "q": f"Fundamental Rights are enshrined in which part of the Constitution of India?",
                    "opts": ["Part I", "Part II", "Part III (Articles 12-35)", "Part IV"],
                    "ans": 2,
                    "sol": "Part III of the Constitution guarantees Fundamental Rights, ensuring equality, freedom, and constitutional remedies.",
                },
                {
                    "q": f"Sustainable development seeks to balance economic growth with:",
                    "opts": ["Unregulated resource depletion", "Environmental protection and resource conservation", "Maximized consumer debt", "Rapid industrial urbanization only"],
                    "ans": 1,
                    "sol": "Sustainable development meets the needs of the present without compromising the ability of future generations to meet their own needs.",
                },
            ]

        # Double bank if count > len(templates)
        while len(templates) < count:
            idx = len(templates) + 1
            templates.append({
                "q": f"Comprehensive Exam Question {idx} on {chapter}: Which key analytical statement is correct?",
                "opts": [
                    f"A) Statement verified in {board} Class {class_num} syllabus",
                    "B) Unverified opposing hypothesis",
                    "C) Arbitrary constant approximation",
                    "D) Discontinuous boundary value"
                ],
                "ans": 0,
                "sol": f"Curriculum statement verified in {board} Class {class_num} textbook guidelines for {chapter}."
            })

        out = []
        for idx in range(count):
            base = templates[idx % len(templates)]
            out.append({
                "id": f"q_{idx+1}",
                "question": base["q"],
                "options": base["opts"],
                "correct_option_index": base["ans"],
                "correct_option": base["opts"][base["ans"]],
                "solution": base["sol"],
            })
        return out

    # =========================================================================
    # A.2) VIDYAFLOW ADAPTIVE QUIZ & ASSESSMENT ENGINE
    # =========================================================================
    def generate_adaptive_quiz(
        self,
        board: str,
        class_level: int,
        subject: str,
        chapter: str,
        concept: Optional[str] = None,
        rag_context: Optional[str] = None,
        difficulty: str = "medium",
        num_questions: int = 5,
        prerequisite_list: Optional[List[str]] = None,
        focus_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes VidyaFlow Master System Prompt for adaptive quiz generation.
        Produces non-repetitive questions categorized by cognitive level (recall,
        understanding, application, analysis) with prerequisite diagnostic tags.
        """
        target_diff = difficulty.lower() if difficulty.lower() in ["easy", "medium", "hard"] else "medium"
        concept_name = concept or chapter
        prereqs = prerequisite_list or ["Foundational Syllabus Definitions", "Standard Units & Equations"]
        skills = focus_skills or ["definition", "numerical-problem", "real-world application", "misconception-check"]
        context_str = (rag_context or "").strip()
        if not context_str:
            context_str = f"{board} Board Class {class_level} {subject} - Chapter: {chapter}. Focus on {concept_name}."

        prompt = VIDYAFLOW_ADAPTIVE_QUIZ_MASTER_SYSTEM_PROMPT.format(
            board_name=board,
            class_level=class_level,
            subject_name=subject,
            chapter_name=chapter,
            concept_name=concept_name,
            prerequisite_list=", ".join(prereqs),
            target_difficulty=target_diff,
            num_questions=num_questions,
            focus_skills=", ".join(skills),
            retrieved_rag_chunks=context_str,
        )

        system_instruction = (
            f"You are VidyaFlow's Principal AI Pedagogy Specialist and Assessment Designer for {board} Class {class_level}. "
            f"Generate high-diversity, textbook-grounded diagnostic questions adhering strictly to JSON output schema."
        )

        try:
            response_text, provider = self.generate_text(prompt, system_instruction=system_instruction)
            if response_text:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list):
                    cleaned_qs = []
                    for idx, q in enumerate(data["questions"], 1):
                        q_type = q.get("question_type", "mcq")
                        if q_type not in ["mcq", "fill_blank", "conceptual_short"]:
                            q_type = "mcq"

                        cog_level = q.get("cognitive_level", "understanding")
                        if cog_level not in ["recall", "understanding", "application", "analysis"]:
                            cog_level = "understanding"

                        raw_opts = q.get("options", [])
                        sanitized_opts = []
                        if isinstance(raw_opts, list):
                            for opt_idx, opt in enumerate(raw_opts):
                                if isinstance(opt, dict):
                                    o_id = str(opt.get("option_id", chr(65 + opt_idx)))
                                    o_text = str(opt.get("text", f"Option {o_id}"))
                                    sanitized_opts.append({"option_id": o_id, "text": o_text})
                                else:
                                    o_id = chr(65 + opt_idx)
                                    sanitized_opts.append({"option_id": o_id, "text": str(opt)})
                        
                        while len(sanitized_opts) < 4:
                            o_id = chr(65 + len(sanitized_opts))
                            sanitized_opts.append({"option_id": o_id, "text": f"Alternative {o_id}"})

                        corr_ans = str(q.get("correct_answer", "A"))
                        if q_type == "mcq" and corr_ans not in [o["option_id"] for o in sanitized_opts]:
                            corr_ans = sanitized_opts[0]["option_id"]

                        cleaned_qs.append({
                            "question_id": str(q.get("question_id", f"q{idx}")),
                            "question_type": q_type,
                            "cognitive_level": cog_level,
                            "difficulty": target_diff,
                            "question_text": str(q.get("question_text", f"Diagnostic question on {concept_name}")),
                            "options": sanitized_opts[:4],
                            "correct_answer": corr_ans,
                            "hint": str(q.get("hint", f"Recall foundational principles of {concept_name}.")),
                            "explanation": str(q.get("explanation", f"Based on {board} Class {class_level} textbook context.")),
                            "prerequisite_concept_tested": str(q.get("prerequisite_concept_tested", prereqs[0])),
                            "root_gap_remediation": str(q.get("root_gap_remediation", f"Review prerequisite topic: {prereqs[0]} before proceeding.")),
                        })

                    if len(cleaned_qs) >= num_questions:
                        return {
                            "concept_id": concept_name,
                            "difficulty_level": target_diff,
                            "total_questions": num_questions,
                            "questions": cleaned_qs[:num_questions],
                        }
        except Exception as e:
            logger.warning(f"generate_adaptive_quiz LLM call failed: {e}. Supplementing with fallback.")

        # Deterministic adaptive quiz fallback
        return self._fallback_adaptive_quiz(
            board=board,
            class_level=class_level,
            subject=subject,
            chapter=chapter,
            concept=concept_name,
            difficulty=target_diff,
            num_questions=num_questions,
            prerequisite_list=prereqs,
            focus_skills=skills,
        )

    def _fallback_adaptive_quiz(
        self,
        board: str,
        class_level: int,
        subject: str,
        chapter: str,
        concept: str,
        difficulty: str,
        num_questions: int,
        prerequisite_list: List[str],
        focus_skills: List[str],
    ) -> Dict[str, Any]:
        """
        Produces high-diversity, pedagogy-grounded questions with cognitive level,
        prerequisite gap tagging, and root remediation when LLM is unavailable.
        """
        sub_lower = subject.lower()
        ch_lower = chapter.lower()

        is_math = "math" in sub_lower or "algebra" in ch_lower or "number" in ch_lower or "geometry" in ch_lower
        is_physics = "physic" in sub_lower or "light" in ch_lower or "motion" in ch_lower or "force" in ch_lower or "electr" in ch_lower
        is_bio = "bio" in sub_lower or "cell" in ch_lower or "plant" in ch_lower or "food" in ch_lower or "life" in ch_lower

        if is_math:
            base_templates = [
                {
                    "type": "mcq",
                    "cog": "understanding",
                    "q": f"When solving an equation involving {concept}, which mathematical property justifies operating on both sides equally?",
                    "opts": ["Addition / Multiplication Property of Equality", "Associative Law only", "Commutative Invariance", "Distributive factoring"],
                    "ans": "A",
                    "hint": "Consider what maintains the equilibrium of the equals sign (=).",
                    "sol": "The properties of equality state that performing identical arithmetic operations on both sides preserves true balance.",
                    "prereq": "Properties of Real Numbers & Equality",
                    "remed": "Review balancing equations and real number arithmetic axioms.",
                },
                {
                    "type": "mcq",
                    "cog": "application",
                    "q": f"A student evaluates (x + y)² for x = 3 and y = 4. What is the value obtained using the standard algebraic identity?",
                    "opts": ["25", "49", "14", "19"],
                    "ans": "B",
                    "hint": "First calculate (3 + 4) or expand x² + 2xy + y².",
                    "sol": "(3 + 4)² = 7² = 49. By identity: 3² + 2(3)(4) + 4² = 9 + 24 + 16 = 49.",
                    "prereq": "Algebraic Expansion & Substitution",
                    "remed": "Re-study the binomial expansion identity (a + b)² = a² + 2ab + b².",
                },
                {
                    "type": "fill_blank",
                    "cog": "analysis",
                    "q": f"In {concept}, a quadratic equation ax² + bx + c = 0 has two distinct real roots if and only if the discriminant b² - 4ac is ______.",
                    "opts": ["Greater than zero (> 0)", "Equal to zero (= 0)", "Less than zero (< 0)", "A negative integer"],
                    "ans": "A",
                    "hint": "Think about whether the square root in the quadratic formula yields a real number.",
                    "sol": "If D = b² - 4ac > 0, the square root yields two distinct non-zero real values, resulting in two real roots.",
                    "prereq": "Quadratic Formula & Square Roots",
                    "remed": "Revisit nature of roots and discriminant analysis.",
                },
                {
                    "type": "mcq",
                    "cog": "recall",
                    "q": f"What is the degree of a non-zero constant polynomial in {board} Class {class_level} Mathematics?",
                    "opts": ["0", "1", "Undefined", "Infinity"],
                    "ans": "A",
                    "hint": "Recall that a constant c can be written as c * x⁰.",
                    "sol": "The exponent of the variable in c * x⁰ is 0, so the degree of a non-zero constant polynomial is 0.",
                    "prereq": "Polynomial Terminology & Exponents",
                    "remed": "Review definition of monomial degrees and zero exponents.",
                },
                {
                    "type": "conceptual_short",
                    "cog": "analysis",
                    "q": f"Identify the common error when expanding -(a - b): A student wrote -a - b. What should the correct expansion be?",
                    "opts": ["-a + b", "-a - b", "a + b", "a - b"],
                    "ans": "A",
                    "hint": "Remember to distribute the negative sign (-1) to both terms inside the parentheses.",
                    "sol": "Distributing -1 gives: (-1)*a + (-1)*(-b) = -a + b (or b - a).",
                    "prereq": "Distributive Property with Negative Signs",
                    "remed": "Practice sign distribution across parentheses.",
                },
            ]
        elif is_physics:
            base_templates = [
                {
                    "type": "mcq",
                    "cog": "understanding",
                    "q": f"In {concept}, when light enters an optically denser medium from air at an oblique angle, why does it bend towards the normal?",
                    "opts": ["Its speed decreases in the denser medium", "Its frequency increases abruptly", "Its wavelength doubles", "Total internal reflection repels it"],
                    "ans": "A",
                    "hint": "Focus on the wave speed change across the boundary according to wave theory.",
                    "sol": "As light enters an optically denser medium, its propagation velocity slows down, causing the wavefront to pivot towards the normal.",
                    "prereq": "Wave Speed & Optical Density",
                    "remed": "Review refractive index definition n = c / v.",
                },
                {
                    "type": "mcq",
                    "cog": "application",
                    "q": f"An optical fiber transmits digital data with zero signal leakage. Which phenomenon is primarily utilized?",
                    "opts": ["Total Internal Reflection", "Diffuse Scattering", "Polarization", "Chromatic Aberration"],
                    "ans": "A",
                    "hint": "The angle of incidence inside the glass core exceeds the critical angle.",
                    "sol": "Total internal reflection keeps light confined inside the core because the core has a higher refractive index than the cladding and angle of incidence > critical angle.",
                    "prereq": "Critical Angle & Boundary Conditions",
                    "remed": "Review total internal reflection criteria.",
                },
                {
                    "type": "fill_blank",
                    "cog": "analysis",
                    "q": f"For a thin convex lens in {concept}, if an object is placed at 2F, the magnification (m) of the real image formed is ______.",
                    "opts": ["-1.0", "+1.0", "+0.5", "-2.0"],
                    "ans": "A",
                    "hint": "The image is real, inverted, and exactly the same size as the object.",
                    "sol": "At 2F, image distance v = 2F. Magnification m = v / u = (2F) / (-2F) = -1.0 (inverted, same size).",
                    "prereq": "Lens Formula & Sign Convention",
                    "remed": "Practice Cartesian sign conventions and ray diagrams for convex lenses.",
                },
                {
                    "type": "mcq",
                    "cog": "recall",
                    "q": f"What is the standard SI unit of optical power of a lens discussed in {concept}?",
                    "opts": ["Dioptre (D)", "Watt (W)", "Joule (J)", "Metre (m)"],
                    "ans": "A",
                    "hint": "Defined as the reciprocal of focal length in metres (1/m).",
                    "sol": "Power of a lens P = 1 / f(in metres), measured in Dioptres (m⁻¹).",
                    "prereq": "SI Metric Units & Focal Length",
                    "remed": "Review unit definitions and power calculation formulas.",
                },
                {
                    "type": "conceptual_short",
                    "cog": "analysis",
                    "q": f"A student measures the refractive index of glass and obtains 0.85. Why is this value physically impossible?",
                    "opts": ["Light cannot travel faster in glass than in vacuum (n must be >= 1)", "Refractive index must always be negative", "Glass cannot refract light", "Measurement has no units"],
                    "ans": "A",
                    "hint": "Remember n = c / v, and c (speed in vacuum) is the universal speed limit.",
                    "sol": "Absolute refractive index n = c / v. Since light cannot exceed c in any medium, v <= c, meaning n must always be >= 1.0.",
                    "prereq": "Universal Speed of Light & Refractive Index",
                    "remed": "Review absolute refractive index derivation from vacuum speed.",
                },
            ]
        elif is_bio:
            base_templates = [
                {
                    "type": "mcq",
                    "cog": "understanding",
                    "q": f"During cellular respiration in {concept}, why are mitochondria referred to as the powerhouse of the cell?",
                    "opts": ["They synthesize ATP through oxidative phosphorylation", "They store hereditary DNA exclusively", "They digest cellular waste products", "They synthesize chloroplasts"],
                    "ans": "A",
                    "hint": "Focus on the chemical energy currency generated for metabolic reactions.",
                    "sol": "Mitochondria generate adenosine triphosphate (ATP), the universal chemical energy carrier used across living cells.",
                    "prereq": "Cell Organelles & Cellular Metabolism",
                    "remed": "Review eukaryotic organelle functions and ATP generation.",
                },
                {
                    "type": "mcq",
                    "cog": "application",
                    "q": f"If stomata in plant leaves are coated with petroleum jelly, which process will be immediately halted?",
                    "opts": ["Transpiration and CO2 gas exchange", "Soil water absorption by root hairs", "Root elongation", "Secondary thickening of wood"],
                    "ans": "A",
                    "hint": "Stomatal pores control the flow of gases into and out of the leaf lamina.",
                    "sol": "Blocking stomata prevents diffusion of carbon dioxide required for photosynthesis and halts transpiration of water vapor.",
                    "prereq": "Leaf Anatomy & Stomatal Transpiration",
                    "remed": "Study stomatal mechanism and gas exchange pathways.",
                },
                {
                    "type": "fill_blank",
                    "cog": "recall",
                    "q": f"In {concept}, green plants absorb light energy primarily using the photosynthetic pigment called ______.",
                    "opts": ["Chlorophyll", "Hemoglobin", "Carotene only", "Anthocyanin"],
                    "ans": "A",
                    "hint": "This magnesium-containing green pigment is located in chloroplast thylakoids.",
                    "sol": "Chlorophyll pigment absorbs solar radiation (chiefly blue and red wavelengths) to drive photosynthetic light reactions.",
                    "prereq": "Photosynthetic Pigments & Chloroplasts",
                    "remed": "Review thylakoid pigments and solar absorption.",
                },
                {
                    "type": "conceptual_short",
                    "cog": "analysis",
                    "q": f"How do xylem vessels differ fundamentally from phloem sieve tubes in plant transport?",
                    "opts": ["Xylem transports water unidirectionally; phloem transports food bidirectionally", "Xylem is living tissue; phloem is dead tissue", "Xylem transports sugars; phloem transports nitrogen only", "There is no difference"],
                    "ans": "A",
                    "hint": "Consider the direction of transport and the nature of the sap transported.",
                    "sol": "Xylem conducts water and inorganic minerals upwards from roots to foliage; phloem translocates soluble organic photoassimilates bidirectionally.",
                    "prereq": "Vascular Plant Tissues (Xylem vs Phloem)",
                    "remed": "Review vascular bundles and unidirectional vs multidirectional translocation.",
                },
                {
                    "type": "mcq",
                    "cog": "application",
                    "q": f"Which blood vessel carries oxygen-rich blood from the lungs directly into the left atrium of the human heart?",
                    "opts": ["Pulmonary Vein", "Pulmonary Artery", "Superior Vena Cava", "Aorta"],
                    "ans": "A",
                    "hint": "Veins carry blood towards the heart; this specific vein is an exception carrying oxygenated blood.",
                    "sol": "The pulmonary veins are unique veins carrying freshly oxygenated blood from the pulmonary capillaries back to the left atrium.",
                    "prereq": "Double Circulation & Heart Anatomy",
                    "remed": "Study pulmonary circulation and cardiac chamber inputs.",
                },
            ]
        else: # Social studies or general
            base_templates = [
                {
                    "type": "mcq",
                    "cog": "understanding",
                    "q": f"What is the foundational principle of Universal Adult Suffrage in {board} Class {class_level} Civics?",
                    "opts": ["Every adult citizen has one vote, and every vote has equal value", "Voting rights depend on property ownership", "Only graduates are permitted to vote", "Voting rights are restricted to urban areas"],
                    "ans": "A",
                    "hint": "Recall the democratic ideal of political equality regardless of caste, gender, or wealth.",
                    "sol": "Universal Adult Suffrage ensures every citizen above 18 years possesses one vote with equal democratic weight.",
                    "prereq": "Democratic Principles & Constitutional Equality",
                    "remed": "Review constitutional articles on fundamental rights and voting franchise.",
                },
                {
                    "type": "mcq",
                    "cog": "application",
                    "q": f"Which sector of the economy does dairy farming, forestry, and mining belong to?",
                    "opts": ["Primary Sector", "Secondary Sector", "Tertiary Sector", "Quaternary Sector"],
                    "ans": "A",
                    "hint": "This sector involves direct exploitation and extraction of natural resources.",
                    "sol": "The primary sector encompasses economic activities that directly depend on natural environmental resources.",
                    "prereq": "Sectors of the Indian Economy",
                    "remed": "Review primary, secondary, and tertiary classification criteria.",
                },
                {
                    "type": "fill_blank",
                    "cog": "recall",
                    "q": f"The Indian standard time meridian passes through Mirzapur (Uttar Pradesh) at longitude ______.",
                    "opts": ["82° 30' E", "68° 7' E", "97° 25' E", "23° 30' N"],
                    "ans": "A",
                    "hint": "It is exactly 5 hours and 30 minutes ahead of Greenwich Mean Time (UTC+05:30).",
                    "sol": "The standard meridian of India is 82° 30' E, selected to maintain a unified standard time across all longitudinal spans.",
                    "prereq": "Indian Geography: Latitudinal & Longitudinal Extent",
                    "remed": "Study Indian time zones and longitude degree calculations.",
                },
                {
                    "type": "conceptual_short",
                    "cog": "analysis",
                    "q": f"Why is sustainable development critical for future generations in economic geography?",
                    "opts": ["It prevents irreversible environmental depletion while supporting economic progress", "It stops all industrial manufacturing", "It exhausts resources as quickly as possible", "It prioritizes short-term profits over health"],
                    "ans": "A",
                    "hint": "Think about balancing present resource utilization with ecological conservation.",
                    "sol": "Sustainable development ensures that economic growth does not deplete renewable and non-renewable natural reserves beyond recovery.",
                    "prereq": "Resource Conservation & Ecological Balance",
                    "remed": "Review sustainable development frameworks and resource management.",
                },
                {
                    "type": "mcq",
                    "cog": "understanding",
                    "q": f"In a parliamentary system of government, who is collectively responsible to the Lok Sabha?",
                    "opts": ["The Council of Ministers headed by the Prime Minister", "The Supreme Court of India", "The Election Commission", "The State Governors"],
                    "ans": "A",
                    "hint": "Article 75(3) of the Constitution mandates this executive accountability.",
                    "sol": "The Council of Ministers remains in power only as long as it enjoys the confidence of the majority of members in the Lok Sabha.",
                    "prereq": "Parliamentary Democracy & Separation of Powers",
                    "remed": "Study executive accountability and parliamentary motions of no-confidence.",
                },
            ]

        # Extend if num_questions > len(base_templates)
        while len(base_templates) < num_questions:
            idx = len(base_templates) + 1
            base_templates.append({
                "type": "mcq",
                "cog": "application",
                "q": f"Question {idx} on {concept}: Which analytical relationship is verified according to {board} Class {class_level} curriculum?",
                "opts": [
                    f"A) Verified standard principle for {concept}",
                    "B) Unverified opposing hypothesis",
                    "C) Discontinuous boundary value",
                    "D) Arbitrary unit assumption",
                ],
                "ans": "A",
                "hint": f"Recall textbook definitions for {concept}.",
                "sol": f"Curriculum guidelines for {board} Class {class_level} {subject} require adherence to verified definitions.",
                "prereq": f"{concept} Core Concepts",
                "remed": f"Review textbook sections for {chapter} - {concept}.",
            })

        questions = []
        for idx in range(num_questions):
            tmpl = base_templates[idx % len(base_templates)]
            raw_opts = tmpl["opts"]
            formatted_opts = [
                {"option_id": chr(65 + o_idx), "text": opt_text}
                for o_idx, opt_text in enumerate(raw_opts)
            ]

            questions.append({
                "question_id": f"q{idx + 1}",
                "question_type": tmpl["type"],
                "cognitive_level": tmpl["cog"],
                "difficulty": difficulty,
                "question_text": tmpl["q"],
                "options": formatted_opts,
                "correct_answer": tmpl["ans"],
                "hint": tmpl["hint"],
                "explanation": tmpl["sol"],
                "prerequisite_concept_tested": tmpl["prereq"],
                "root_gap_remediation": tmpl["remed"],
            })

        return {
            "concept_id": concept,
            "difficulty_level": difficulty,
            "total_questions": num_questions,
            "questions": questions,
        }

    # =========================================================================
    # B) TEACHER WORKSHEET GENERATOR
    # =========================================================================
    def generate_worksheet(
        self,
        board: str,
        class_num: int,
        subject: str,
        chapter: str,
        difficulty: str = "Medium",
        counts: Optional[Dict[str, int]] = None,
        context_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates a print-ready school worksheet with Sections A, B, C and Answer Key.
        """
        counts = counts or {"mcq": 5, "short_answer": 3, "long_answer": 2}
        num_mcq = counts.get("mcq", 5)
        num_short = counts.get("short_answer", 3)
        num_long = counts.get("long_answer", 2)

        context_str = "\n\n".join(context_chunks or [])
        if not context_str.strip():
            context_str = f"{board} Board Class {class_num} syllabus for {subject} - {chapter}."

        prompt = f"""You are a master teacher curriculum creator for {board} Board (Class {class_num}).
Create a comprehensive, printable student examination worksheet and teacher answer key for:
Subject: {subject}
Chapter: {chapter}
Difficulty: {difficulty}

Target Counts:
- Section A (MCQs): {num_mcq} questions (1 mark each)
- Section B (Short Answer): {num_short} questions (2-3 marks each)
- Section C (Long Answer / Problem Solving): {num_long} questions (5 marks each)

Curriculum context from official textbooks:
{context_str}

STRICT JSON OUTPUT REQUIREMENT:
Return ONLY valid JSON matching this structure:
{{
  "title": "{board} Board - Class {class_num} {subject} Practice Worksheet",
  "board": "{board}",
  "class_num": {class_num},
  "subject": "{subject}",
  "chapter": "{chapter}",
  "difficulty": "{difficulty}",
  "total_marks": {num_mcq * 1 + num_short * 3 + num_long * 5},
  "sections": {{
    "section_a_mcq": [
      {{ "question_number": 1, "question": "Question text", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "marks": 1 }}
    ],
    "section_b_short_answer": [
      {{ "question_number": {num_mcq + 1}, "question": "Short concept question?", "marks": 3 }}
    ],
    "section_c_long_answer": [
      {{ "question_number": {num_mcq + num_short + 1}, "question": "Comprehensive analytical problem or proof?", "marks": 5 }}
    ]
  }},
  "answer_key": {{
    "section_a_mcq": [
      {{ "question_number": 1, "answer": "B) ...", "explanation": "Why correct" }}
    ],
    "section_b_short_answer": [
      {{ "question_number": {num_mcq + 1}, "answer": "Key points required", "steps": ["Point 1", "Point 2"] }}
    ],
    "section_c_long_answer": [
      {{ "question_number": {num_mcq + num_short + 1}, "answer": "Complete step-by-step model solution", "steps": ["Derivation step 1", "Formula step 2", "Final conclusion"] }}
    ]
  }}
}}
"""
        response_text, provider = self.generate_text(
            prompt,
            system_instruction=f"You create official curriculum worksheets for {board} Board Class {class_num}. Always return clean structured JSON."
        )

        if response_text:
            try:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict) and "sections" in data and "answer_key" in data:
                    return data
            except Exception as e:
                logger.warning(f"Could not parse LLM worksheet output: {e}. Building structured template.")

        # Deterministic Worksheet Fallback
        return self._fallback_worksheet(board, class_num, subject, chapter, difficulty, num_mcq, num_short, num_long)

    def _fallback_worksheet(
        self, board: str, class_num: int, subject: str, chapter: str, difficulty: str, mcq_count: int, short_count: int, long_count: int
    ) -> Dict[str, Any]:
        """Provides high-quality structured worksheet matching school assessment standards."""
        sec_a = []
        ans_a = []
        for i in range(1, mcq_count + 1):
            sec_a.append({
                "question_number": i,
                "question": f"Identify the fundamental property or rule governing {chapter} (Concept {i}).",
                "options": [
                    f"A) Primary standard rule defined in {board} Class {class_num} syllabus",
                    "B) Secondary observational property",
                    "C) Inverse relationship condition",
                    "D) Dependent experimental outcome"
                ],
                "marks": 1,
            })
            ans_a.append({
                "question_number": i,
                "answer": f"A) Primary standard rule defined in {board} Class {class_num} syllabus",
                "explanation": f"Corresponds to the standard theorem and definitions in {chapter}."
            })

        sec_b = []
        ans_b = []
        q_start = mcq_count + 1
        for i in range(q_start, q_start + short_count):
            sec_b.append({
                "question_number": i,
                "question": f"State two essential applications or worked examples demonstrating {chapter}.",
                "marks": 3,
            })
            ans_b.append({
                "question_number": i,
                "answer": f"Clear statement of principle and two distinct applications in {subject}.",
                "steps": [
                    "1. Define the fundamental concept clearly with scientific/mathematical notation.",
                    "2. State application 1 with reference to everyday physical phenomena or equations.",
                    "3. Verify dimensions/units or substitute values to confirm consistency."
                ]
            })

        sec_c = []
        ans_c = []
        q_start_c = q_start + short_count
        for i in range(q_start_c, q_start_c + long_count):
            sec_c.append({
                "question_number": i,
                "question": f"Derive the general equation or explain the complete mechanism of {chapter} with a labeled diagram or step-by-step proof.",
                "marks": 5,
            })
            ans_c.append({
                "question_number": i,
                "answer": f"Comprehensive derivation and analytical breakdown for {chapter}.",
                "steps": [
                    "State initial assumptions and draw standard schematic diagram.",
                    "Apply fundamental laws (e.g. conservation principles or algebraic expansion).",
                    "Express the final derived formula clearly with SI units and state boundary conditions."
                ]
            })

        return {
            "title": f"{board} Board - Class {class_num} {subject} Worksheet: {chapter}",
            "board": board,
            "class_num": class_num,
            "subject": subject,
            "chapter": chapter,
            "difficulty": difficulty,
            "total_marks": mcq_count * 1 + short_count * 3 + long_count * 5,
            "sections": {
                "section_a_mcq": sec_a,
                "section_b_short_answer": sec_b,
                "section_c_long_answer": sec_c,
            },
            "answer_key": {
                "section_a_mcq": ans_a,
                "section_b_short_answer": ans_b,
                "section_c_long_answer": ans_c,
            },
        }

    # =========================================================================
    # C) AI CHATBOT (SYLLABUS DOUBT RESOLVER)
    # =========================================================================
    def answer_doubt(
        self,
        question: str,
        board: str,
        class_num: int,
        subject: str,
        retrieved_passages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Answers a student's doubt strictly using retrieved textbook context.
        Prevents hallucinations and cites exact chapter sources.
        """
        sources = list(dict.fromkeys([
            f"{p.get('chapter', 'Chapter Content')} ({p.get('board', board)} Class {p.get('class', class_num)})"
            for p in retrieved_passages if p.get("chapter")
        ]))

        if not sources:
            sources = [f"{subject} - General Concepts ({board} Class {class_num})"]

        context_texts = [p.get("text", "") for p in retrieved_passages if p.get("text")]
        combined_context = "\n\n---\n\n".join(context_texts)

        prompt = f"""You are the VidyaFlow AI Learning Coach for {board} Board, Class {class_num} {subject}.
A student asked: "{question}"

TEXTBOOK CONTEXT:
{combined_context}

STRICT INSTRUCTIONS:
1. Answer clearly, accurately, and kindly at a Class {class_num} level.
2. Ground your answer strictly in the provided textbook context to prevent hallucinations.
3. If the context does not contain sufficient information, state clearly what the textbook covers and guide the student.
4. Highlight key formulas, definitions, and rules in bold or bullet points.
"""
        response_text, provider = self.generate_text(
            prompt,
            system_instruction=f"You are a dedicated tutor for {board} Class {class_num} {subject}. Be encouraging, concise, and 100% truthful to syllabus data."
        )

        if not response_text:
            # High-relevance fallback explanation based on retrieved passages
            if context_texts:
                response_text = f"According to your official {board} Class {class_num} textbook for {subject}:\n\n" + context_texts[0][:400] + "..."
            else:
                response_text = f"In {board} Class {class_num} {subject}, {question} is an important concept. Review your prescribed textbook chapter for detailed definitions and worked examples."

        return {
            "answer": response_text.strip(),
            "sources": sources,
            "provider": provider,
        }

    # =========================================================================
    # D) QUIZ EVALUATOR
    # =========================================================================
    def evaluate_quiz_answer(
        self,
        question_id: str,
        selected_option: str,
        correct_option: str,
    ) -> Dict[str, Any]:
        """
        Validates student answer and provides instant feedback with score update.
        """
        sel_clean = (selected_option or "").strip().lower()
        cor_clean = (correct_option or "").strip().lower()

        # Check exact or contained match
        is_correct = (sel_clean == cor_clean) or (
            len(cor_clean) > 3 and cor_clean in sel_clean
        ) or (
            len(sel_clean) > 3 and sel_clean in cor_clean
        )

        explanation = (
            f"Correct! '{selected_option}' is the right answer according to the curriculum textbook."
            if is_correct
            else f"Not quite. The correct answer is '{correct_option}'. Review the step-by-step solution to understand the underlying principle."
        )

        return {
            "question_id": question_id,
            "correct": is_correct,
            "selected_option": selected_option,
            "correct_option": correct_option,
            "explanation": explanation,
            "score_delta": 1 if is_correct else 0,
            "total_score": 1 if is_correct else 0,
        }

    # =========================================================================
    # E) LESSON OVERVIEW & AI CONCEPT CARDS
    # =========================================================================
    def generate_lesson_overview(
        self,
        board: str,
        class_num: int,
        subject: str,
        chapter: str,
        context_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates comprehensive chapter summary (3 full paragraphs), 5-8 structured
        key concept cards with definitions, formulas, and real-world examples,
        and an actionable prescribed next step.
        """
        context_str = "\n\n---\n\n".join(context_chunks or [])
        if not context_str.strip():
            context_str = f"Syllabus Topic: {board} Board, Class {class_num}, Subject: {subject}, Chapter: {chapter}."

        prompt = f"""You are a master curriculum pedagogy expert and textbook author for {board} Board (Class {class_num}).
Analyze the textbook context and provide an in-depth lesson overview for:
Subject: {subject}
Chapter: {chapter}

OFFICIAL TEXTBOOK PASSAGES:
{context_str}

STRICT JSON OUTPUT REQUIREMENT:
Return ONLY a valid JSON object. Do not include markdown code fences or conversational text.
Format strictly as:
{{
  "chapter_summary": "Comprehensive 3-paragraph detailed summary.\\n\\nParagraph 1: Foundational context, syllabus scope, and formal definitions.\\n\\nParagraph 2: Core mathematical equations, physical/chemical/biological laws, properties, and governing principles.\\n\\nParagraph 3: Practical real-world engineering or natural applications, common exam questions, and problem-solving strategies.",
  "key_concepts": [
    {{
      "id": "concept_1",
      "title": "Specific Conceptual Principle",
      "summary": "Detailed multi-sentence explanation of this concept.",
      "definition": "Precise textbook definition in academic standard language.",
      "formula": "Standard mathematical/scientific formula with units (or key principle).",
      "real_world_example": "Concrete technological or everyday application.",
      "key_points": [
        "Core rule or condition",
        "Common board exam point",
        "High-yield calculation or diagram note"
      ]
    }}
  ],
  "prescribed_next_step": "Explicit guidance on what the student should review next based on syllabus progression (e.g., Master derivations in Concept 2, complete the 8 flashcards, then take the 10-question practice quiz).",
  "recommended_learning_path": [
    "Step 1: Read the 3-paragraph Chapter Summary and Key Concept Cards",
    "Step 2: Flip through the active-recall flashcard deck (target 100% recall)",
    "Step 3: Solve the in-lesson Quick Quiz",
    "Step 4: Launch full board practice exam in the Practice Arena"
  ]
}}
"""
        system_instruction = (
            f"You are a Senior Academic Specialist for {board} Board Class {class_num} {subject}. "
            f"Ground your summary and concept breakdown strictly in verified textbook passages and output valid JSON."
        )

        try:
            response_text, provider = self.generate_text(prompt, system_instruction=system_instruction)
            if response_text:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict):
                    # Extract or sanitize fields
                    chap_summary = str(data.get("chapter_summary") or "").strip()
                    prescribed = str(data.get("prescribed_next_step") or "").strip()
                    raw_concepts = data.get("key_concepts") or data.get("concept_cards") or []

                    if isinstance(raw_concepts, list) and len(raw_concepts) >= 3:
                        cleaned_concepts = []
                        for idx, item in enumerate(raw_concepts, 1):
                            title = str(item.get("title", f"Core Concept {idx}"))
                            summary = str(item.get("summary", ""))
                            definition = str(item.get("definition", summary[:120]))
                            formula = str(item.get("formula", f"Governing formula for {chapter}"))
                            example = str(item.get("real_world_example", f"Practical application in {subject}"))
                            kp = [str(p) for p in item.get("key_points", []) if p]

                            cleaned_concepts.append({
                                "id": str(item.get("id", f"concept_{idx}")),
                                "title": title,
                                "summary": summary,
                                "definition": definition,
                                "formula": formula,
                                "real_world_example": example,
                                "key_points": kp if kp else [f"Essential curriculum point for {title}"],
                                "formulas_or_definitions": [definition, formula],
                                "source_reference": str(item.get("source_reference", f"{board} Class {class_num} {subject}")),
                            })

                        if not chap_summary:
                            chap_summary = self._build_deterministic_summary(board, class_num, subject, chapter, context_chunks)
                        if not prescribed:
                            prescribed = f"Master the definitions and formulas in the {len(cleaned_concepts)} concept cards above, then test active recall using the interactive flashcard deck."

                        path = [str(s) for s in data.get("recommended_learning_path", []) if s]
                        if not path:
                            path = [
                                f"Review the 3-paragraph summary and core formulas for {chapter}",
                                "Flip through interactive flashcards to test active recall",
                                "Attempt the in-lesson 10-question practice quiz",
                                "Generate full board-level assignment in Practice Arena"
                            ]

                        return {
                            "chapter": chapter,
                            "subject": subject,
                            "board": board,
                            "class_num": class_num,
                            "chapter_summary": chap_summary,
                            "key_concepts": cleaned_concepts,
                            "concept_cards": cleaned_concepts,  # Backwards compatibility
                            "prescribed_next_step": prescribed,
                            "recommended_learning_path": path,
                        }
        except Exception as e:
            logger.warning(f"Failed to generate lesson overview LLM response: {e}. Using deterministic curriculum fallback.")

        # Deterministic syllabus fallback
        return self._fallback_lesson_overview(board, class_num, subject, chapter, context_chunks)

    def _build_deterministic_summary(
        self, board: str, class_num: int, subject: str, chapter: str, context_chunks: Optional[List[str]]
    ) -> str:
        """Constructs a comprehensive, rich 3-paragraph chapter summary."""
        excerpt = " ".join([c.strip() for c in (context_chunks or [])[:2]])
        if len(excerpt) > 280:
            excerpt = excerpt[:280] + "..."
        elif not excerpt:
            excerpt = f"The curriculum outlines the foundational principles, analytical properties, and core theorems governing {chapter}."

        p1 = (
            f"{chapter} constitutes a cornerstone module within the {board} Board Class {class_num} {subject} curriculum. "
            f"The chapter establishes rigorous foundational terminology and theoretical frameworks, introducing students to core definitions, "
            f"scientific axioms, and syllabus standards. Context excerpt: {excerpt}"
        )
        p2 = (
            f"From an analytical standpoint, this chapter elucidates the mathematical formulations, governing laws, and equilibrium conditions "
            f"that dictate how {chapter} operates in both ideal and practical environments. Students are expected to comprehend governing equations, "
            f"verify dimensional homogeneity across derived units, and master the step-by-step methodologies required to solve standard numerical "
            f"and conceptual problems prescribed in official examinations."
        )
        p3 = (
            f"In practical terms, the principles of {chapter} find extensive application across contemporary engineering, medical diagnostics, "
            f"and environmental sciences. To achieve complete mastery, students must focus on distinguishing common exam misconceptions, drawing neat "
            f"standard diagrams, and progressing through the structured active-recall cards and practice assessments provided in this module."
        )
        return f"{p1}\n\n{p2}\n\n{p3}"

    def _fallback_lesson_overview(
        self, board: str, class_num: int, subject: str, chapter: str, context_chunks: Optional[List[str]]
    ) -> Dict[str, Any]:
        """High-quality deterministic 3-paragraph summary and 6 detailed concept cards."""
        source = f"{board} Class {class_num} {subject} - {chapter}"
        summary_text = self._build_deterministic_summary(board, class_num, subject, chapter, context_chunks)

        concepts = [
            {
                "id": "concept_1",
                "title": f"1. Foundational Principles & Scope of {chapter}",
                "summary": f"Introduces the formal definitions, physical meaning, and standard terminology of {chapter} according to {board} Class {class_num} standards.",
                "definition": f"{chapter} represents the systematic study of foundational principles and relations established in the {board} syllabus.",
                "formula": "Standard formal identity and axiomatic definition verified in syllabus text.",
                "real_world_example": f"Applied across foundational scientific models and engineering systems.",
                "key_points": [
                    "Memorize exact standard textbook definitions without omitting key technical terms.",
                    "Verify baseline conditions before applying standard formulas.",
                    "Pay strict attention to standard SI units and dimensional parameters."
                ],
                "formulas_or_definitions": [
                    f"Formal definition of {chapter} according to {board} Board guidelines."
                ],
                "source_reference": source,
            },
            {
                "id": "concept_2",
                "title": "2. Governing Laws & Analytical Formulations",
                "summary": "Covers the mathematical relationships, conservation principles, and functional dependencies that govern problem solving.",
                "definition": "Equations and functional dependencies that quantify interactions between primary variables in this topic.",
                "formula": "Primary governing equation: verify balance of LHS and RHS dimensions.",
                "real_world_example": "Used by engineers and scientists to model rates of change and equilibrium states.",
                "key_points": [
                    "State the governing law verbatim in board examinations.",
                    "Always list given parameters, required variables, and intermediate steps.",
                    "Dimensional consistency must be checked prior to final numerical calculation."
                ],
                "formulas_or_definitions": [
                    "Governing mathematical equations and standard balance relations."
                ],
                "source_reference": source,
            },
            {
                "id": "concept_3",
                "title": "3. Conditions, Constraints & Boundary Rules",
                "summary": "Examines the limiting conditions, threshold constraints, and critical values where behaviors change qualitatively.",
                "definition": "Threshold conditions under which theoretical relationships hold valid or undergo transition.",
                "formula": "Critical boundary threshold condition: Value >= Threshold limit.",
                "real_world_example": "Critical thresholds in optical fibers, electrical circuit breakers, or chemical equilibrium.",
                "key_points": [
                    "Identify whether initial conditions meet required boundary parameters.",
                    "Distinguish between continuous variation and sudden phase/regime transitions.",
                    "High-frequency theme for Section B short-answer and reasoning questions."
                ],
                "formulas_or_definitions": [
                    "Threshold criterion and boundary equations."
                ],
                "source_reference": source,
            },
            {
                "id": "concept_4",
                "title": "4. Laboratory & Experimental Verification",
                "summary": "Describes the standard laboratory setup, observation methods, control of variables, and graphical analysis.",
                "definition": "Empirical methodology employed to confirm theoretical predictions through controlled measurement.",
                "formula": "Error equation: Percentage Error = (|Experimental - Theoretical| / Theoretical) * 100%.",
                "real_world_example": "Bench experiments in school physics and chemistry laboratories.",
                "key_points": [
                    "Draw neat labeled diagrams showing apparatus layout and pointer alignments.",
                    "Record independent, dependent, and controlled variables in tabular format.",
                    "Take repeated readings to minimize random experimental errors."
                ],
                "formulas_or_definitions": [
                    "Experimental data reduction and graphical slope equations."
                ],
                "source_reference": source,
            },
            {
                "id": "concept_5",
                "title": "5. Real-World Applications & Technological Impact",
                "summary": "Bridges textbook theory with modern industrial, environmental, and technological applications.",
                "definition": "Translation of fundamental scientific principles into functional technologies and devices.",
                "formula": "Efficiency / Output ratio = (Useful Output / Total Input) * 100%.",
                "real_world_example": "Modern telecommunications, renewable power grids, biotechnology, and infrastructure.",
                "key_points": [
                    "Connect abstract concepts to tangible devices used in everyday life.",
                    "Crucial for high-order thinking skill (HOTS) questions in Section C.",
                    "Explain the operating principle clearly before citing specific use-cases."
                ],
                "formulas_or_definitions": [
                    "Application operating principle and system efficiency formulation."
                ],
                "source_reference": source,
            },
            {
                "id": "concept_6",
                "title": "6. High-Yield Exam Strategy & Common Pitfalls",
                "summary": "Summarizes the most frequent student mistakes, mark allocation rubrics, and high-yield scoring tips.",
                "definition": "Pedagogical checklist designed to prevent loss of marks during board evaluations.",
                "formula": "Scoring Rubric: Definition (1m) + Formula & Units (1m) + Working (2m) + Diagram (1m).",
                "real_world_example": "Standard marking schemes applied in TS and ICSE evaluators' answer keys.",
                "key_points": [
                    "Never omit SI units in the final statement of a numerical problem.",
                    "Always label rays, axes, and arrowheads clearly on all diagrams.",
                    "Complete all 8 interactive flashcards to cement active memory retention."
                ],
                "formulas_or_definitions": [
                    "Exam scoring rubric and verification checklist."
                ],
                "source_reference": source,
            },
        ]

        prescribed = (
            f"Thoroughly review the 3-paragraph summary and 6 Concept Cards above for {chapter}. "
            f"Next, flip through the active-recall flashcard deck (target 100% accuracy), and attempt the 10 practice questions in the Practice Arena."
        )

        return {
            "chapter": chapter,
            "subject": subject,
            "board": board,
            "class_num": class_num,
            "chapter_summary": summary_text,
            "key_concepts": concepts,
            "concept_cards": concepts,  # Backwards compatibility
            "prescribed_next_step": prescribed,
            "recommended_learning_path": [
                f"1. Read the 3-paragraph summary and core formulas for {chapter}",
                "2. Master the 6 detailed Key Concept Cards above",
                "3. Flip through the 8-10 interactive active-recall flashcards",
                "4. Launch the Practice Arena to solve 10-20 curriculum questions",
            ],
        }

    # =========================================================================
    # F) INTERACTIVE FLASHCARDS (8-10 Robust Flashcards)
    # =========================================================================
    def generate_flashcards(
        self,
        board: str,
        class_num: int,
        subject: str,
        chapter: str,
        context_chunks: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates 8 to 10 interactive study flashcards from RAG textbook context.
        Each card has id, concept_tag, front (prompt/question), back (definition/answer), and summary.
        """
        context_str = "\n\n---\n\n".join(context_chunks or [])
        if not context_str.strip():
            context_str = f"Syllabus Topic: {board} Board, Class {class_num}, Subject: {subject}, Chapter: {chapter}."

        prompt = f"""You are a master educator for {board} Board (Class {class_num}).
Create between 8 and 10 robust, highly effective active-recall study flashcards for:
Subject: {subject}
Chapter: {chapter}

OFFICIAL TEXTBOOK PASSAGES:
{context_str}

STRICT JSON OUTPUT REQUIREMENT:
Return ONLY a valid JSON array of objects. Do not include markdown code fences or introductory text.
Format each flashcard strictly as:
[
  {{
    "id": "fc_1",
    "concept_tag": "Specific Sub-Topic or Principle",
    "concept": "Specific Sub-Topic or Principle",
    "front": "Clear, direct question or test prompt on the front of the card",
    "back": "Concise, 1-2 sentence precise answer, formula, or law on the back of the card",
    "summary": "1-sentence pedagogical takeaway"
  }}
]
"""
        system_instruction = (
            f"You are an Academic Specialist creating memory-retention flashcards for {board} Class {class_num} {subject}. "
            f"Provide at least 8 cards covering core definitions, formulas, units, and common misconceptions. Return strict JSON."
        )

        response_text, provider = self.generate_text(prompt, system_instruction=system_instruction)

        if response_text:
            try:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict) and "flashcards" in data:
                    data = data["flashcards"]
                if isinstance(data, list) and len(data) >= 6:
                    cleaned = []
                    for idx, item in enumerate(data, 1):
                        concept_val = str(item.get("concept_tag") or item.get("concept") or chapter)
                        cleaned.append({
                            "id": str(item.get("id", f"fc_{idx}")),
                            "concept_tag": concept_val,
                            "concept": concept_val,
                            "front": str(item.get("front", f"Key concept prompt {idx}")),
                            "back": str(item.get("back", f"Key concept definition {idx}")),
                            "summary": str(item.get("summary", f"Core syllabus principle for {chapter}.")),
                        })
                    if cleaned:
                        return cleaned
            except Exception as e:
                logger.warning(f"Failed to parse flashcards LLM response: {e}")

        # Deterministic fallback flashcards
        return self._fallback_flashcards(board, class_num, subject, chapter, context_chunks)

    def _fallback_flashcards(
        self, board: str, class_num: int, subject: str, chapter: str, context_chunks: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Fallback 8-card flashcard set when LLM generation is unavailable."""
        return [
            {
                "id": "fc_1",
                "concept_tag": "Core Definition",
                "concept": f"{chapter} - Definition",
                "front": f"What is the formal definition of {chapter} in {board} Class {class_num} {subject}?",
                "back": f"{chapter} establishes fundamental laws and relationships governing {subject.lower()} systems and formal problem-solving.",
                "summary": "Fundamental definition required for definition questions.",
            },
            {
                "id": "fc_2",
                "concept_tag": "Governing Law",
                "concept": "Governing Law / Principle",
                "front": f"State the primary governing law or axiom related to {chapter}.",
                "back": f"All processes in {chapter} obey conservation principles and established mathematical/physical relations.",
                "summary": "Core law frequently examined in Section A and B.",
            },
            {
                "id": "fc_3",
                "concept_tag": "Formulas & Equations",
                "concept": "Mathematical Representation",
                "front": f"What are the primary formulas and equations used to solve problems in {chapter}?",
                "back": "Refer to official syllabus formulas: verify dimensional balance, variables, and sign conventions.",
                "summary": "Essential for multi-step numerical calculations.",
            },
            {
                "id": "fc_4",
                "concept_tag": "Units & Dimensions",
                "concept": "Standard SI Units",
                "front": "What standard SI units and dimensional parameters apply in this chapter?",
                "back": "Standard SI units apply (e.g., metre, second, kilogram, Newton, Joule, Pascal) with standard metric prefixes.",
                "summary": "Always include units in final answers to avoid mark deductions.",
            },
            {
                "id": "fc_5",
                "concept_tag": "Experimental Observation",
                "concept": "Laboratory & Practical Work",
                "front": f"What is the key experimental verification or practical observation associated with {chapter}?",
                "back": "Controlled experiments verify theoretical predictions while keeping confounding variables constant.",
                "summary": "Crucial for diagram and experiment-based questions.",
            },
            {
                "id": "fc_6",
                "concept_tag": "Common Misconception",
                "concept": "Frequent Student Pitfall",
                "front": f"What is a common error or misconception to avoid when answering questions on {chapter}?",
                "back": "Confusing scalar and vector quantities, omitting units, or misapplying boundary conditions.",
                "summary": "High-yield correction to boost exam accuracy.",
            },
            {
                "id": "fc_7",
                "concept_tag": "Real-World Application",
                "concept": "Practical Applications",
                "front": f"Where is {chapter} applied in daily life or modern technology?",
                "back": "Applied across modern engineering, telecommunications, medical diagnostics, and household utilities.",
                "summary": "Frequently tested in application-oriented (HOTS) questions.",
            },
            {
                "id": "fc_8",
                "concept_tag": "Exam Strategy",
                "concept": "Scoring High Marks",
                "front": f"How should you structure a long-answer response for {chapter}?",
                "back": "State the law/definition first, draw a neat labeled diagram, write the formula, and show step-by-step substitution.",
                "summary": "Standard marking rubric for maximum score.",
            },
        ]

    # =========================================================================
    # G) ONE-CLICK TEACHER ASSIGNMENT GENERATOR
    # =========================================================================
    def generate_teacher_assignment(
        self,
        board: str,
        class_num: int,
        subject: str,
        chapter: str,
        difficulty: str = "Medium",
        assignment_title: Optional[str] = None,
        context_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates a complete 25-mark assignment in a single click without HTTP errors:
        - Section A: 5 MCQs (1 mark each = 5 marks)
        - Section B: 5 Short Answer Questions (2 marks each = 10 marks)
        - Section C: 2 HOTS / Application Questions (5 marks each = 10 marks)
        - Teacher Answer Key with step-by-step solutions and marking rubrics for every question.
        """
        import uuid
        context_str = "\n\n---\n\n".join(context_chunks or [])
        if not context_str.strip():
            context_str = f"Syllabus Topic: {board} Board, Class {class_num}, Subject: {subject}, Chapter: {chapter}."

        title = assignment_title or f"Class {class_num} {subject} Assessment: {chapter}"

        prompt = f"""You are a Master Head of Department and Senior Examiner for {board} Board (Class {class_num}).
Generate a complete, high-quality, 25-mark examination packet / assessment for:
Subject: {subject}
Chapter: {chapter}
Difficulty: {difficulty}

OFFICIAL TEXTBOOK PASSAGES:
{context_str}

STRICT JSON OUTPUT REQUIREMENT:
Return ONLY a valid JSON object matching the exact structure below. Do not include markdown fences.
{{
  "title": "{title}",
  "total_marks": 25,
  "estimated_duration_minutes": 45,
  "instructions": [
    "All questions are compulsory.",
    "Section A carries 5 marks (5 MCQs, 1 mark each).",
    "Section B carries 10 marks (5 Short Answer questions, 2 marks each).",
    "Section C carries 10 marks (2 HOTS / Application questions, 5 marks each).",
    "Draw neat labeled diagrams wherever necessary."
  ],
  "section_a": [
    {{
      "q_num": 1,
      "question": "Question text here?",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_option": "A) ...",
      "marks": 1
    }}
  ],
  "section_b": [
    {{
      "q_num": 6,
      "question": "Concise conceptual question?",
      "marks": 2,
      "expected_length": "2 to 3 sentences with formula"
    }}
  ],
  "section_c": [
    {{
      "q_num": 11,
      "question": "High-order thinking skill / numerical derivation question?",
      "marks": 5,
      "sub_parts": ["(a) State the principle (2 marks)", "(b) Calculate or derive (3 marks)"]
    }}
  ],
  "teacher_answer_key": {{
    "section_a": [
      {{"q_num": 1, "answer": "Option letter", "explanation": "Why correct"}}
    ],
    "section_b": [
      {{"q_num": 6, "model_answer": "Model answer points", "marking_scheme": "1 mark for definition, 1 mark for example or formula"}}
    ],
    "section_c": [
      {{"q_num": 11, "model_answer": "Complete derivation and final calculation with units", "marking_scheme": "2 marks for formula, 2 marks for substitution, 1 mark for final answer with units"}}
    ]
  }},
  "grading_rubric": [
    {{"score_range": "22-25", "grade": "A+", "feedback": "Outstanding conceptual mastery and analytical precision."}},
    {{"score_range": "18-21", "grade": "A", "feedback": "Strong understanding; minor calculation or unit errors."}},
    {{"score_range": "13-17", "grade": "B", "feedback": "Adequate foundation; revisit derivations and Section C problems."}},
    {{"score_range": "Below 13", "grade": "C", "feedback": "Needs targeted remediation on core chapter definitions."}}
  ]
}}
"""
        system_instruction = (
            f"You are a Senior Academic Examiner for {board} Board Class {class_num} {subject}. "
            f"Generate a rigorous, authentic curriculum assignment packet with complete teacher key. Return strict JSON."
        )

        try:
            response_text, provider = self.generate_text(prompt, system_instruction=system_instruction)
            if response_text:
                data = extract_json_from_text(response_text)
                if isinstance(data, dict):
                    sec_a = data.get("section_a") or data.get("section_a_mcqs") or []
                    sec_b = data.get("section_b") or data.get("section_b_short_answers") or []
                    sec_c = data.get("section_c") or data.get("section_c_hots") or []

                    if len(sec_a) >= 4 and len(sec_b) >= 3 and len(sec_c) >= 1:
                        data["assignment_id"] = f"asg_{uuid.uuid4().hex[:8]}"
                        data["board"] = board
                        data["class_num"] = class_num
                        data["subject"] = subject
                        data["chapter"] = chapter
                        data["difficulty"] = difficulty
                        data["total_marks"] = 25
                        data["created_at"] = "2026-10-31"

                        # Ensure both aliases exist
                        data["section_a"] = sec_a
                        data["section_a_mcqs"] = sec_a
                        data["section_b"] = sec_b
                        data["section_b_short_answers"] = sec_b
                        data["section_c"] = sec_c
                        data["section_c_hots"] = sec_c

                        return data
        except Exception as e:
            logger.warning(f"Failed to parse teacher assignment LLM response: {e}. Using deterministic curriculum fallback.")

        # Deterministic fallback assignment packet
        return self._fallback_teacher_assignment(board, class_num, subject, chapter, difficulty, title)

    def _fallback_teacher_assignment(
        self, board: str, class_num: int, subject: str, chapter: str, difficulty: str, title: str
    ) -> Dict[str, Any]:
        """Deterministic ready-to-assign teacher packet aligned to curriculum standards (Total: 25 marks)."""
        import uuid

        section_a = [
            {
                "q_num": 1,
                "question": f"Which fundamental principle governs the physical/mathematical behavior of {chapter} in {board} Class {class_num}?",
                "options": ["A) Law of Conservation", "B) Principle of Superposition", "C) Axiomatic Equilibrium", "D) Inverse Proportionality"],
                "correct_option": "A) Law of Conservation",
                "marks": 1
            },
            {
                "q_num": 2,
                "question": f"What is the standard SI unit associated with the primary variable in {chapter}?",
                "options": ["A) Joule (J)", "B) Newton (N)", "C) Pascal (Pa)", "D) Standard derived SI unit"],
                "correct_option": "D) Standard derived SI unit",
                "marks": 1
            },
            {
                "q_num": 3,
                "question": f"When solving numerical problems in {chapter}, which initial condition must always be verified?",
                "options": ["A) Dimensional homogeneity", "B) Boundary velocity", "C) Arbitrary constant", "D) Ambient temperature"],
                "correct_option": "A) Dimensional homogeneity",
                "marks": 1
            },
            {
                "q_num": 4,
                "question": f"Which of the following conditions represents an ideal theoretical state in {chapter}?",
                "options": ["A) Negligible resistive loss / zero friction", "B) Maximum entropy", "C) Open circuit divergence", "D) Infinite resistance"],
                "correct_option": "A) Negligible resistive loss / zero friction",
                "marks": 1
            },
            {
                "q_num": 5,
                "question": f"What is the primary distinguishing characteristic of {chapter} in official board examinations?",
                "options": ["A) Multi-variable dependency and rigorous derivations", "B) Pure arbitrary memorization", "C) Constant discontinuous rate", "D) Disregard for sign conventions"],
                "correct_option": "A) Multi-variable dependency and rigorous derivations",
                "marks": 1
            }
        ]

        section_b = [
            {
                "q_num": 6,
                "question": f"State the formal textbook definition of {chapter} and write down its primary mathematical/physical equation.",
                "marks": 2,
                "expected_length": "2 to 3 sentences with formula"
            },
            {
                "q_num": 7,
                "question": f"Give two real-world technological or natural examples illustrating the direct application of {chapter}.",
                "marks": 2,
                "expected_length": "2 concise bullet points"
            },
            {
                "q_num": 8,
                "question": f"Explain why units and dimensional consistency are vital when computing final answers in {chapter}.",
                "marks": 2,
                "expected_length": "2 sentences"
            },
            {
                "q_num": 9,
                "question": f"What is a common misconception or calculation pitfall students encounter in {chapter}, and how can it be avoided?",
                "marks": 2,
                "expected_length": "2 to 3 sentences"
            },
            {
                "q_num": 10,
                "question": f"State the sign convention or boundary rules required when substituting numerical values into {chapter} formulas.",
                "marks": 2,
                "expected_length": "2 sentences with convention rule"
            }
        ]

        section_c = [
            {
                "q_num": 11,
                "question": f"A system governed by the principles of {chapter} is investigated under laboratory conditions. Derive the governing formula from first principles and analyze limiting conditions.",
                "marks": 5,
                "sub_parts": [
                    "(a) State assumptions and draw a neat labeled diagram (2 marks).",
                    "(b) Show complete mathematical derivation step-by-step and state two practical limitations (3 marks)."
                ]
            },
            {
                "q_num": 12,
                "question": f"An experimental investigation on {chapter} yields numerical data with a 12% deviation from theoretical predictions. Identify possible error sources and design a corrective analytical method.",
                "marks": 5,
                "sub_parts": [
                    "(a) Identify two systematic or environmental error sources (2 marks).",
                    "(b) Propose corrective laboratory modifications and calculate adjusted values (3 marks)."
                ]
            }
        ]

        teacher_answer_key = {
            "section_a": [
                {"q_num": 1, "answer": "A", "explanation": "Conservation principles form the foundation of this curriculum chapter."},
                {"q_num": 2, "answer": "D", "explanation": "Derived standard SI units are required per syllabus standards."},
                {"q_num": 3, "answer": "A", "explanation": "All equations must balance dimensionally prior to numerical substitution."},
                {"q_num": 4, "answer": "A", "explanation": "Theoretical models assume negligible frictional or resistive losses."},
                {"q_num": 5, "answer": "A", "explanation": "Advanced Class level curriculum introduces coupled variables and proofs."}
            ],
            "section_b": [
                {"q_num": 6, "model_answer": f"Definition: Formal statement from {board} textbook. Formula: Stated clearly with all symbols defined.", "marking_scheme": "1 mark for definition, 1 mark for correct formula with symbols."},
                {"q_num": 7, "model_answer": "Example 1: Technological application. Example 2: Industrial or natural phenomenon.", "marking_scheme": "1 mark per accurate example with brief context."},
                {"q_num": 8, "model_answer": "Dimensional consistency ensures that only physically meaningful quantities of identical units are equated or added.", "marking_scheme": "1 mark for concept, 1 mark for explanation."},
                {"q_num": 9, "model_answer": "Frequent error: Omitting metric conversions (e.g. cm to m) or sign conventions. Avoidance: Convert all inputs to base SI units before calculating.", "marking_scheme": "1 mark for identifying error, 1 mark for solution."},
                {"q_num": 10, "model_answer": "Cartesian sign convention: Distances measured along incident direction are positive; opposite are negative.", "marking_scheme": "1 mark for convention statement, 1 mark for diagram/rule."}
            ],
            "section_c": [
                {"q_num": 11, "model_answer": "Part (a): Neat labeled diagram with coordinate axes (2 marks). Part (b): Step-by-step mathematical substitution, arriving at final expression with stated boundary conditions (3 marks).", "marking_scheme": "Part (a): 2 marks, Part (b): 3 marks."},
                {"q_num": 12, "model_answer": "Part (a): Calibration drift or parallax observation error (2 marks). Part (b): Repeated trials, zero-error correction, and percent error formula application (3 marks).", "marking_scheme": "Part (a): 2 marks, Part (b): 3 marks."}
            ]
        }

        grading_rubric = [
            {"score_range": "22-25", "grade": "A+", "feedback": "Outstanding conceptual mastery and analytical precision."},
            {"score_range": "18-21", "grade": "A", "feedback": "Strong understanding; minor calculation or unit errors."},
            {"score_range": "13-17", "grade": "B", "feedback": "Adequate foundation; revisit derivations and Section C problems."},
            {"score_range": "Below 13", "grade": "C", "feedback": "Needs targeted remediation on core chapter definitions."}
        ]

        return {
            "assignment_id": f"asg_{uuid.uuid4().hex[:8]}",
            "title": title,
            "board": board,
            "class_num": class_num,
            "subject": subject,
            "chapter": chapter,
            "difficulty": difficulty,
            "total_marks": 25,
            "estimated_duration_minutes": 45,
            "instructions": [
                "All questions are compulsory.",
                "Section A carries 5 marks (5 MCQs, 1 mark each).",
                "Section B carries 10 marks (5 Short Answer questions, 2 marks each).",
                "Section C carries 10 marks (2 HOTS / Application questions, 5 marks each).",
                "Draw neat labeled diagrams and show all intermediate working."
            ],
            "section_a": section_a,
            "section_a_mcqs": section_a,
            "section_b": section_b,
            "section_b_short_answers": section_b,
            "section_c": section_c,
            "section_c_hots": section_c,
            "teacher_answer_key": teacher_answer_key,
            "grading_rubric": grading_rubric,
            "created_at": "2026-10-31"
        }
