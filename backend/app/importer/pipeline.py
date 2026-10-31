import csv
import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models import (
    Board,
    SyllabusVersion,
    ClassGrade,
    Subject,
    Chapter,
    Topic,
    LearningObjective,
    SourceAttribution,
    Lesson,
    WorkedExample,
    PracticeQuestion,
    QuestionOption,
    PrerequisiteRelationship,
)
from app.importer.validator import validate_curriculum_payload, ValidationError


class ImportReport(BaseModel):
    success: bool
    source_file: Optional[str] = None
    boards_created: int = 0
    boards_updated: int = 0
    syllabus_versions_created: int = 0
    subjects_created: int = 0
    subjects_updated: int = 0
    chapters_created: int = 0
    chapters_updated: int = 0
    topics_created: int = 0
    topics_updated: int = 0
    learning_objectives_created: int = 0
    lessons_created: int = 0
    worked_examples_created: int = 0
    questions_created: int = 0
    options_created: int = 0
    prerequisites_created: int = 0
    skipped_count: int = 0
    failed_records: List[Dict[str, Any]] = []

    @property
    def total_imported(self) -> int:
        return (
            self.boards_created
            + self.subjects_created
            + self.chapters_created
            + self.topics_created
            + self.learning_objectives_created
            + self.lessons_created
            + self.worked_examples_created
            + self.questions_created
        )

    @property
    def total_updated(self) -> int:
        return (
            self.boards_updated
            + self.subjects_updated
            + self.chapters_updated
            + self.topics_updated
        )


class CurriculumImporter:
    """
    Robust, idempotent importer for structured curriculum files.
    Supports both JSON tree hierarchies and CSV tabular formats.
    """

    def __init__(self, db: Session):
        self.db = db

    def ensure_class_grades(self):
        """Pre-seeds standard Class 6 to 10 grades if missing."""
        for grade in range(6, 11):
            existing = self.db.query(ClassGrade).filter_by(grade_number=grade).first()
            if not existing:
                cg = ClassGrade(
                    grade_number=grade,
                    code=f"CLASS_{grade}",
                    name=f"Class {grade}",
                    stage="Middle School" if grade <= 8 else "Secondary",
                )
                self.db.add(cg)
        self.db.commit()

    def import_from_json(self, file_path: str) -> ImportReport:
        if not os.path.exists(file_path):
            report = ImportReport(success=False, source_file=file_path)
            report.failed_records.append({"error": f"File not found: {file_path}"})
            return report

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        report = self.import_from_dict(data)
        report.source_file = file_path
        return report

    def import_from_dict(self, data: Dict[str, Any]) -> ImportReport:
        report = ImportReport(success=True)

        # 1. Validate payload structure
        is_valid, validation_errors = validate_curriculum_payload(data)
        if not is_valid:
            report.success = False
            for err in validation_errors:
                report.failed_records.append({"type": "validation_error", "message": err})
            return report

        self.ensure_class_grades()

        try:
            # 2. Source Attribution metadata
            source_meta = data.get("source_attribution")
            source_attr = None
            if source_meta:
                source_attr = (
                    self.db.query(SourceAttribution)
                    .filter_by(
                        title=source_meta.get("title", "Curriculum Guidelines"),
                        publisher=source_meta.get("publisher", "Official Board"),
                    )
                    .first()
                )
                if not source_attr:
                    source_attr = SourceAttribution(
                        source_type=source_meta.get("source_type", "official_textbook"),
                        publisher=source_meta.get("publisher", "Official Board"),
                        publication_year=source_meta.get("publication_year", 2024),
                        edition=source_meta.get("edition"),
                        title=source_meta.get("title", "Curriculum Guidelines"),
                        page_reference=source_meta.get("page_reference"),
                        license_or_permission_status=source_meta.get(
                            "license_or_permission_status", "public_curriculum_framework"
                        ),
                        verification_status=source_meta.get("verification_status", "verified"),
                        verified_by=source_meta.get("verified_by"),
                    )
                    self.db.add(source_attr)
                    self.db.flush()

            # 3. Board
            board_data = data["board"]
            board = self.db.query(Board).filter_by(code=board_data["code"]).first()
            if not board:
                board = Board(
                    code=board_data["code"],
                    name=board_data["name"],
                    full_name=board_data.get("full_name"),
                    country=board_data.get("country", "India"),
                    state_or_region=board_data.get("state_or_region"),
                    is_active=board_data.get("is_active", True),
                )
                self.db.add(board)
                self.db.flush()
                report.boards_created += 1
            else:
                board.name = board_data["name"]
                board.full_name = board_data.get("full_name", board.full_name)
                board.state_or_region = board_data.get("state_or_region", board.state_or_region)
                self.db.flush()
                report.boards_updated += 1

            # 4. Syllabus Version
            syllabus_version = None
            syllabus_code = data.get("syllabus_version", "2024-2025")
            if syllabus_code:
                syllabus_version = (
                    self.db.query(SyllabusVersion)
                    .filter_by(board_id=board.id, version_code=syllabus_code)
                    .first()
                )
                if not syllabus_version:
                    syllabus_version = SyllabusVersion(
                        board_id=board.id,
                        version_code=syllabus_code,
                        academic_year=syllabus_code,
                        description=f"Academic syllabus version {syllabus_code}",
                        is_current=True,
                    )
                    self.db.add(syllabus_version)
                    self.db.flush()
                    report.syllabus_versions_created += 1

            # Map for resolving prerequisite topic codes
            topic_code_to_id: Dict[str, int] = {}
            pending_prerequisites: List[Dict[str, Any]] = []

            # 5. Process Classes & Subjects
            for cls_data in data.get("classes", []):
                grade_num = cls_data["grade_number"]
                class_grade = self.db.query(ClassGrade).filter_by(grade_number=grade_num).first()
                if not class_grade:
                    report.failed_records.append(
                        {"type": "missing_class", "grade": grade_num, "message": f"Class {grade_num} not found"}
                    )
                    continue

                for subj_data in cls_data.get("subjects", []):
                    # Idempotent subject lookup by code or (board, class, name)
                    subject = (
                        self.db.query(Subject)
                        .filter(
                            (Subject.code == subj_data["code"])
                            | (
                                (Subject.board_id == board.id)
                                & (Subject.class_id == class_grade.id)
                                & (Subject.name == subj_data["name"])
                            )
                        )
                        .first()
                    )

                    if not subject:
                        subject = Subject(
                            board_id=board.id,
                            class_id=class_grade.id,
                            syllabus_version_id=syllabus_version.id if syllabus_version else None,
                            code=subj_data["code"],
                            name=subj_data["name"],
                            category=subj_data.get("category", "STEM"),
                            description=subj_data.get("description"),
                        )
                        self.db.add(subject)
                        self.db.flush()
                        report.subjects_created += 1
                    else:
                        subject.code = subj_data["code"]
                        subject.category = subj_data.get("category", subject.category)
                        subject.description = subj_data.get("description", subject.description)
                        self.db.flush()
                        report.subjects_updated += 1

                    # 6. Process Chapters
                    for ch_data in subj_data.get("chapters", []):
                        ch_num = ch_data["chapter_number"]
                        ch_code = ch_data["code"]

                        chapter = (
                            self.db.query(Chapter)
                            .filter(
                                (Chapter.subject_id == subject.id)
                                & ((Chapter.chapter_number == ch_num) | (Chapter.code == ch_code))
                            )
                            .first()
                        )

                        if not chapter:
                            chapter = Chapter(
                                subject_id=subject.id,
                                chapter_number=ch_num,
                                code=ch_code,
                                title=ch_data["title"],
                                description=ch_data.get("description"),
                                estimated_minutes=ch_data.get("estimated_minutes", 90),
                                order_index=ch_data.get("order_index", ch_num),
                                verification_status=ch_data.get("verification_status", "verified"),
                            )
                            self.db.add(chapter)
                            self.db.flush()
                            report.chapters_created += 1
                        else:
                            chapter.code = ch_code
                            chapter.chapter_number = ch_num
                            chapter.title = ch_data["title"]
                            chapter.description = ch_data.get("description", chapter.description)
                            chapter.estimated_minutes = ch_data.get(
                                "estimated_minutes", chapter.estimated_minutes
                            )
                            chapter.verification_status = ch_data.get(
                                "verification_status", chapter.verification_status
                            )
                            self.db.flush()
                            report.chapters_updated += 1

                        # Chapter Learning Objectives
                        for obj_idx, obj_data in enumerate(ch_data.get("learning_objectives", [])):
                            existing_obj = (
                                self.db.query(LearningObjective)
                                .filter_by(chapter_id=chapter.id, code=obj_data.get("code", f"{ch_code}_OBJ_{obj_idx+1}"))
                                .first()
                            )
                            if not existing_obj:
                                lo = LearningObjective(
                                    chapter_id=chapter.id,
                                    code=obj_data.get("code", f"{ch_code}_OBJ_{obj_idx+1}"),
                                    description=obj_data["description"] if isinstance(obj_data, dict) else str(obj_data),
                                    bloom_taxonomy_level=obj_data.get("bloom_taxonomy_level", "understand") if isinstance(obj_data, dict) else "understand",
                                    order_index=obj_idx + 1,
                                )
                                self.db.add(lo)
                                report.learning_objectives_created += 1

                        # 7. Process Topics
                        for t_idx, t_data in enumerate(ch_data.get("topics", [])):
                            t_code = t_data["topic_code"]
                            topic = (
                                self.db.query(Topic)
                                .filter_by(chapter_id=chapter.id, topic_code=t_code)
                                .first()
                            )

                            if not topic:
                                topic = Topic(
                                    chapter_id=chapter.id,
                                    topic_code=t_code,
                                    title=t_data["title"],
                                    description=t_data.get("description"),
                                    order_index=t_data.get("order_index", t_idx + 1),
                                    estimated_minutes=t_data.get("estimated_minutes", 30),
                                    verification_status=t_data.get("verification_status", "verified"),
                                )
                                self.db.add(topic)
                                self.db.flush()
                                report.topics_created += 1
                            else:
                                topic.title = t_data["title"]
                                topic.description = t_data.get("description", topic.description)
                                topic.estimated_minutes = t_data.get(
                                    "estimated_minutes", topic.estimated_minutes
                                )
                                self.db.flush()
                                report.topics_updated += 1

                            topic_code_to_id[t_code] = topic.id

                            # Topic Learning Objectives
                            for to_idx, to_data in enumerate(t_data.get("learning_objectives", [])):
                                to_code = to_data.get("code", f"{t_code}_OBJ_{to_idx+1}")
                                existing_to = (
                                    self.db.query(LearningObjective)
                                    .filter_by(topic_id=topic.id, code=to_code)
                                    .first()
                                )
                                if not existing_to:
                                    tlo = LearningObjective(
                                        topic_id=topic.id,
                                        code=to_code,
                                        description=to_data["description"] if isinstance(to_data, dict) else str(to_data),
                                        bloom_taxonomy_level=to_data.get("bloom_taxonomy_level", "understand") if isinstance(to_data, dict) else "understand",
                                        order_index=to_idx + 1,
                                    )
                                    self.db.add(tlo)
                                    report.learning_objectives_created += 1

                            # Lessons
                            for l_idx, l_data in enumerate(t_data.get("lessons", [])):
                                existing_lesson = (
                                    self.db.query(Lesson)
                                    .filter_by(topic_id=topic.id, title=l_data["title"], section_type=l_data.get("section_type", "explanation"))
                                    .first()
                                )
                                if not existing_lesson:
                                    lesson = Lesson(
                                        topic_id=topic.id,
                                        source_attribution_id=source_attr.id if source_attr else None,
                                        syllabus_version_id=syllabus_version.id if syllabus_version else None,
                                        section_type=l_data.get("section_type", "explanation"),
                                        title=l_data["title"],
                                        content=l_data["content"],
                                        summary=l_data.get("summary"),
                                        language=l_data.get("language", "en"),
                                        reading_time_minutes=l_data.get("reading_time_minutes", 5),
                                        order_index=l_idx + 1,
                                        verification_status=l_data.get("verification_status", "verified"),
                                    )
                                    self.db.add(lesson)
                                    report.lessons_created += 1

                            # Worked Examples
                            for we_idx, we_data in enumerate(t_data.get("worked_examples", [])):
                                existing_we = (
                                    self.db.query(WorkedExample)
                                    .filter_by(topic_id=topic.id, example_number=we_data.get("example_number", we_idx + 1))
                                    .first()
                                )
                                if not existing_we:
                                    we = WorkedExample(
                                        topic_id=topic.id,
                                        source_attribution_id=source_attr.id if source_attr else None,
                                        example_number=we_data.get("example_number", we_idx + 1),
                                        problem_statement=we_data["problem_statement"],
                                        step_by_step_solution=we_data["step_by_step_solution"],
                                        verification_step=we_data.get("verification_step"),
                                        key_takeaway=we_data.get("key_takeaway"),
                                        language=we_data.get("language", "en"),
                                        verification_status=we_data.get("verification_status", "verified"),
                                    )
                                    self.db.add(we)
                                    report.worked_examples_created += 1

                            # Practice Questions
                            for q_idx, q_data in enumerate(t_data.get("practice_questions", [])):
                                q_code = q_data.get("question_code", f"{t_code}_Q_{q_idx+1}")
                                existing_q = (
                                    self.db.query(PracticeQuestion)
                                    .filter_by(topic_id=topic.id, question_code=q_code)
                                    .first()
                                )
                                if not existing_q:
                                    question = PracticeQuestion(
                                        topic_id=topic.id,
                                        source_attribution_id=source_attr.id if source_attr else None,
                                        question_code=q_code,
                                        question_text=q_data["question_text"],
                                        question_type=q_data.get("question_type", "multiple_choice"),
                                        difficulty_level=q_data.get("difficulty_level", "medium"),
                                        marks=q_data.get("marks", 1),
                                        hint=q_data.get("hint"),
                                        worked_explanation=q_data.get("worked_explanation", ""),
                                        correct_answer=str(q_data.get("correct_answer", "")),
                                        language=q_data.get("language", "en"),
                                        verification_status=q_data.get("verification_status", "verified"),
                                    )
                                    self.db.add(question)
                                    self.db.flush()
                                    report.questions_created += 1

                                    # Question Options
                                    for opt_idx, opt in enumerate(q_data.get("options", [])):
                                        if isinstance(opt, dict):
                                            opt_text = opt["option_text"]
                                            is_correct = opt.get("is_correct", False)
                                            feedback = opt.get("feedback")
                                        else:
                                            opt_text = str(opt)
                                            is_correct = str(opt_idx) == str(q_data.get("correct_answer")) or opt_text == str(q_data.get("correct_answer"))
                                            feedback = None

                                        q_opt = QuestionOption(
                                            question_id=question.id,
                                            option_index=opt_idx,
                                            option_text=opt_text,
                                            is_correct=is_correct,
                                            feedback=feedback,
                                        )
                                        self.db.add(q_opt)
                                        report.options_created += 1

                            # Save prerequisite definitions for post-processing
                            if "prerequisites" in t_data:
                                for pre_code in t_data["prerequisites"]:
                                    pending_prerequisites.append(
                                        {
                                            "target_topic_code": t_code,
                                            "prerequisite_topic_code": pre_code,
                                            "relationship_type": "required",
                                        }
                                    )

            # 8. Post-process Prerequisite Relationships
            for pre in pending_prerequisites:
                target_id = topic_code_to_id.get(pre["target_topic_code"])
                req_id = topic_code_to_id.get(pre["prerequisite_topic_code"])

                if not req_id:
                    # Try finding in database
                    req_topic = self.db.query(Topic).filter_by(topic_code=pre["prerequisite_topic_code"]).first()
                    if req_topic:
                        req_id = req_topic.id

                if target_id and req_id and target_id != req_id:
                    existing_rel = (
                        self.db.query(PrerequisiteRelationship)
                        .filter_by(target_topic_id=target_id, prerequisite_topic_id=req_id)
                        .first()
                    )
                    if not existing_rel:
                        pr = PrerequisiteRelationship(
                            target_topic_id=target_id,
                            prerequisite_topic_id=req_id,
                            relationship_type=pre["relationship_type"],
                        )
                        self.db.add(pr)
                        report.prerequisites_created += 1

            self.db.commit()
            return report

        except Exception as e:
            self.db.rollback()
            report.success = False
            report.failed_records.append({"type": "database_error", "message": str(e)})
            return report

    def import_from_csv(self, file_path: str) -> ImportReport:
        """
        Imports curriculum from a flat CSV file.
        Required columns:
          board_code, board_name, grade_number, subject_code, subject_name,
          chapter_number, chapter_code, chapter_title
        Optional columns:
          topic_code, topic_title, estimated_minutes, syllabus_version
        """
        report = ImportReport(success=True, source_file=file_path)
        if not os.path.exists(file_path):
            report.success = False
            report.failed_records.append({"error": f"File not found: {file_path}"})
            return report

        self.ensure_class_grades()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader):
                    board_code = row.get("board_code", "").strip()
                    board_name = row.get("board_name", board_code).strip()
                    grade_str = row.get("grade_number", "").strip()
                    subject_code = row.get("subject_code", "").strip()
                    subject_name = row.get("subject_name", "").strip()
                    ch_num_str = row.get("chapter_number", "").strip()
                    ch_code = row.get("chapter_code", "").strip()
                    ch_title = row.get("chapter_title", "").strip()

                    if not (board_code and grade_str and subject_code and ch_num_str and ch_code and ch_title):
                        report.skipped_count += 1
                        report.failed_records.append(
                            {"row": row_idx + 2, "error": "Missing required fields in CSV row"}
                        )
                        continue

                    grade_num = int(grade_str)
                    ch_num = int(ch_num_str)

                    # Board
                    board = self.db.query(Board).filter_by(code=board_code).first()
                    if not board:
                        board = Board(code=board_code, name=board_name)
                        self.db.add(board)
                        self.db.flush()
                        report.boards_created += 1

                    # Class
                    cg = self.db.query(ClassGrade).filter_by(grade_number=grade_num).first()
                    if not cg:
                        continue

                    # Subject
                    subject = (
                        self.db.query(Subject)
                        .filter_by(board_id=board.id, class_id=cg.id, code=subject_code)
                        .first()
                    )
                    if not subject:
                        subject = Subject(
                            board_id=board.id,
                            class_id=cg.id,
                            code=subject_code,
                            name=subject_name,
                        )
                        self.db.add(subject)
                        self.db.flush()
                        report.subjects_created += 1

                    # Chapter
                    chapter = (
                        self.db.query(Chapter)
                        .filter_by(subject_id=subject.id, code=ch_code)
                        .first()
                    )
                    if not chapter:
                        chapter = Chapter(
                            subject_id=subject.id,
                            chapter_number=ch_num,
                            code=ch_code,
                            title=ch_title,
                            estimated_minutes=int(row.get("estimated_minutes", 90)),
                        )
                        self.db.add(chapter)
                        self.db.flush()
                        report.chapters_created += 1
                    else:
                        chapter.title = ch_title
                        report.chapters_updated += 1

                    # Optional topic
                    t_code = row.get("topic_code", "").strip()
                    t_title = row.get("topic_title", "").strip()
                    if t_code and t_title:
                        topic = self.db.query(Topic).filter_by(chapter_id=chapter.id, topic_code=t_code).first()
                        if not topic:
                            topic = Topic(
                                chapter_id=chapter.id,
                                topic_code=t_code,
                                title=t_title,
                            )
                            self.db.add(topic)
                            self.db.flush()
                            report.topics_created += 1
                        else:
                            topic.title = t_title
                            report.topics_updated += 1

            self.db.commit()
            return report

        except Exception as e:
            self.db.rollback()
            report.success = False
            report.failed_records.append({"type": "csv_import_error", "message": str(e)})
            return report
