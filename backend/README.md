# VidyaFlow — Curriculum Database and Backend Foundation

This directory contains the Python FastAPI backend and database architecture for **VidyaFlow**, an adaptive learning platform for Classes 6–10 covering the **Telangana State Board** and **ICSE**.

---

## 1. Architecture Overview

- **Framework**: FastAPI (asynchronous, OpenAPI/Swagger auto-documentation)
- **ORM & Models**: SQLAlchemy 2.0 (normalized relational schema, PostgreSQL-compatible, SQLite local fallback)
- **Migrations**: Alembic (version-controlled schema migrations)
- **Validation & Serialization**: Pydantic v2 schemas
- **Testing**: pytest & httpx TestClient
- **Data Ingestion**: Idempotent curriculum importer pipeline supporting JSON hierarchies and CSV tabular formats

---

## 2. Curriculum Data Model

The database schema is fully normalized and organized around official curriculum structures:

| Model | Table | Description |
|---|---|---|
| `Board` | `boards` | Education board (Telangana State Board, ICSE) |
| `SyllabusVersion` | `syllabus_versions` | Academic year and revision (e.g., 2024–2025) |
| `ClassGrade` | `class_grades` | Academic levels (Classes 6 to 10) |
| `Subject` | `subjects` | Subjects linked to board, class, and syllabus |
| `Chapter` | `chapters` | Chapters with number, code, title, and estimated minutes |
| `Topic` | `topics` | Fine-grained concepts with hierarchical subtopic support |
| `LearningObjective` | `learning_objectives` | Measurable objectives with Bloom's taxonomy tags |
| `SourceAttribution` | `source_attributions` | Publisher, textbook title, edition, and verification status |
| `Lesson` | `lessons` | Conceptual content sections (explanation, key concepts, recap) with language tag |
| `WorkedExample` | `worked_examples` | Step-by-step problem statements, solutions, and verification |
| `PracticeQuestion` | `practice_questions` | Practice items with question type, difficulty, hints, and worked explanations |
| `QuestionOption` | `question_options` | Distractor and correct options for multiple-choice questions |
| `PrerequisiteRelationship` | `prerequisite_relationships` | Directed prerequisite graph for the adaptive learning map |

---

## 3. Quickstart & Installation

### Prerequisites
- Python 3.10+ (tested with Python 3.12 and 3.13)
- Windows / macOS / Linux

### Setup Virtual Environment
```bash
cd backend
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# Install dependencies:
pip install -r requirements.txt
```

### Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default `.env` configuration uses SQLite for instant local execution:
```env
DATABASE_URL="sqlite:///./vidyaflow.db"
```
To connect PostgreSQL in staging or production, simply configure:
```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/vidyaflow"
```

---

## 4. Database Migrations & Seeding

### Run Alembic Migrations
```bash
alembic upgrade head
```

### Seed Verified Curriculum Metadata
Populates official Telangana State Board and ICSE Class 6–10 chapter structures:
```bash
python -m app.cli.seed
```

### Import Custom Curriculum Files
You can import any structured JSON or CSV file using the CLI tool:
```bash
# JSON hierarchy:
python -m app.cli.import_curriculum data/sample_curriculum_import.json

# Flat CSV:
python -m app.cli.import_curriculum path/to/curriculum.csv
```
The importer validates all relationships, detects intra-file duplicates, and performs safe, idempotent upserts without creating duplicate chapters.

---

## 5. Starting the Server

```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger UI: **http://localhost:8000/docs**
- ReDoc Documentation: **http://localhost:8000/redoc**
- Health check: **http://localhost:8000/health**

---

## 6. Implemented API Endpoints

### Health & Root
- `GET /health` — Application and database connection health check
- `GET /api/v1/health` — API v1 health check

### Boards & Classes
- `GET /api/v1/boards` — List all education boards (`?is_active=true`)
- `GET /api/v1/boards/{board_id}` — Retrieve a board by ID
- `GET /api/v1/classes` — List supported classes (Classes 6 to 10)
- `GET /api/v1/boards/{board_id}/classes` — List classes configured for a specific board

### Subjects & Chapters
- `GET /api/v1/subjects` — Filter subjects by `board_id`, `board_code`, `class_grade`, or `category`
- `GET /api/v1/subjects/{subject_id}` — Retrieve subject details including all chapter summaries
- `GET /api/v1/chapters` — List chapters for a subject (`?subject_id=...&limit=...&offset=...`)
- `GET /api/v1/chapters/{chapter_id}` — Retrieve chapter details with topics and learning objectives

### Topics & Content
- `GET /api/v1/topics/{topic_id}` — Retrieve topic detail with lessons, worked examples, and prerequisites
- `GET /api/v1/topics/{topic_id}/lessons` — Retrieve conceptual lessons for a topic (`?language=en`)
- `GET /api/v1/topics/{topic_id}/questions` — Retrieve practice questions with options, hints, and explanations (`?difficulty=medium&limit=20`)

### Search
- `GET /api/v1/search` — Search curriculum content across chapters, topics, lessons, and learning objectives with breadcrumbs and pagination (`?query=...&class_grade=10`)

---

## 7. Automated Tests

Run the complete test suite:
```bash
pytest -v
```
All 15 automated test cases verify:
1. `test_models.py`: Database models, unique constraints, and foreign key cascades
2. `test_importer.py`: Duplicate detection, structural schema validation, safe idempotent re-imports, and CSV ingestion
3. `test_api.py`: Endpoint contracts, filtering, chapter detail retrieval, question option delivery, and full-text curriculum search

---

## 8. Curriculum Data Status & Next Steps

### Currently Verified & Seeded:
- **Telangana State Board (SCERT)**:
  - Official Class 10 Mathematics (14 chapters)
  - Official Class 10 Physical Science (12 chapters)
  - Official Class 10 Biological Science (10 chapters)
  - Official Class 9 Mathematics (14 chapters)
  - Official Class 8 Mathematics (12 chapters)
  - Official Class 7 Mathematics (5 core chapters)
  - Official Class 6 Mathematics (5 core chapters)
- **ICSE (CISCE)**:
  - Official Class 10 Mathematics (19 chapters)
  - Official Class 9 Mathematics (10 chapters)
  - Official Class 8, 7, 6 Mathematics core syllabus
- **Deep Topic & Practice Prototype**:
  - Linear Equations in One Variable & Rational Numbers (lessons, worked examples, hints, and practice questions matching frontend interaction)

### Content Sourcing Roadmap for Subsequent Phases:
1. Sourcing full topic-level breakdowns for Class 6–9 Telangana Social Studies and Languages (Telugu, Hindi).
2. Sourcing full ICSE Physics, Chemistry, and Biology syllabus breakdown for Classes 9 and 10.
3. Ingesting open textbook lesson explanations in Telugu and Hindi for multilingual student support.
4. Expanding prerequisite mapping across multiple grade levels (e.g., Class 7 Integers $\rightarrow$ Class 8 Rational Numbers $\rightarrow$ Class 10 Real Numbers).
