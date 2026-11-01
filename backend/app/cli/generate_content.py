"""
VidyaFlow Content Generation Pipeline CLI.

Batch generates question pools and mind maps for curriculum chapters across
Telangana and ICSE boards (Classes 6-10).
Resumable, idempotent, quota-safe, and generates comprehensive generation_report.json.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.curriculum import Board, Chapter, ClassGrade, Subject
from app.models.quiz import ChapterMindMap, Concept, Question
from app.services.concept_mapper import ensure_chapter_concepts, normalize_board_code
from app.services.gemini_service import GeminiQuotaError, GeminiService
from app.services.mindmap_generator import generate_chapter_mindmap
from app.services.pool_generator import generate_chapter_pool, get_target_distribution
from app.services.quiz_engine import QuizEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_content")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VidyaFlow Content Generation Pipeline")
    parser.add_argument(
        "--board",
        type=str,
        default="all",
        help="Board filter: TS | ICSE | all (default: all)",
    )
    parser.add_argument(
        "--class",
        dest="class_num",
        type=str,
        default="all",
        help="Class filter: 6..10 | all (default: all)",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default="all",
        help="Subject name filter (e.g. Mathematics, Physics, all; default: all)",
    )
    parser.add_argument(
        "--chapter-id",
        type=int,
        default=None,
        help="Single chapter ID mode",
    )
    parser.add_argument(
        "--what",
        type=str,
        choices=["questions", "mindmaps", "both"],
        default="both",
        help="What to generate: questions | mindmaps | both (default: both)",
    )
    parser.add_argument(
        "--target-per-chapter",
        type=int,
        default=30,
        help="Total question target per chapter pool (default: 30)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum chapters to process (useful for test / pilot runs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making LLM calls or DB writes",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Hard safety cap on cumulative LLM calls across the run",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of mindmaps or questions even if existing",
    )
    return parser.parse_args()


def get_ordered_chapters(
    db: Session,
    board: str = "all",
    class_num: str = "all",
    subject: str = "all",
    chapter_id: Optional[int] = None,
) -> List[Chapter]:
    """
    Retrieve chapters prioritized by user specifications:
    1. All Class 8 chapters (both boards).
    2. Mathematics (Classes 6, 7, 9, 10).
    3. Physics / Physical Science (Classes 6, 7, 9, 10).
    4. Biology / Biological Science (Classes 6, 7, 9, 10).
    5. Social Studies (Classes 6, 7, 9, 10).
    """
    is_class_8 = case(
        (ClassGrade.grade_number == 8, 0),
        else_=1,
    )

    subject_priority = case(
        (Subject.name.ilike("%math%"), 1),
        (or_(Subject.name.ilike("%phys%"), Subject.name.ilike("%physical%")), 2),
        (
            or_(
                Subject.name.ilike("%bio%"),
                Subject.name.ilike("%chem%"),
                Subject.name.ilike("%sci%"),
            ),
            3,
        ),
        (Subject.name.ilike("%social%"), 4),
        else_=5,
    )

    class_priority = case(
        (ClassGrade.grade_number == 8, 0),
        (ClassGrade.grade_number == 6, 1),
        (ClassGrade.grade_number == 7, 2),
        (ClassGrade.grade_number == 9, 3),
        (ClassGrade.grade_number == 10, 4),
        else_=5,
    )

    query = (
        db.query(Chapter)
        .join(Subject, Chapter.subject_id == Subject.id)
        .join(ClassGrade, Subject.class_id == ClassGrade.id)
        .join(Board, Subject.board_id == Board.id)
    )

    if chapter_id is not None:
        query = query.filter(Chapter.id == chapter_id)
        return query.all()

    if board.lower() != "all":
        b_norm = normalize_board_code(board)
        query = query.filter(Board.code.ilike(f"%{b_norm}%"))

    if class_num.lower() != "all":
        try:
            c_int = int(class_num)
            query = query.filter(ClassGrade.grade_number == c_int)
        except ValueError:
            pass

    if subject.lower() != "all":
        query = query.filter(Subject.name.ilike(f"%{subject.strip()}%"))

    query = query.order_by(
        is_class_8,
        subject_priority,
        class_priority,
        Board.code,
        Chapter.chapter_number,
        Chapter.id,
    )
    return query.all()


def execute_pipeline(args: argparse.Namespace) -> int:
    db: Session = SessionLocal()
    report_file = "generation_report.json"

    try:
        # Step 0: Ensure all chapter concepts exist
        if not args.dry_run:
            ensure_chapter_concepts(db)

        # Retrieve prioritized chapters
        chapters = get_ordered_chapters(
            db,
            board=args.board,
            class_num=args.class_num,
            subject=args.subject,
            chapter_id=args.chapter_id,
        )

        if args.limit:
            chapters = chapters[: args.limit]

        total_chapters = len(chapters)
        logger.info("Found %d chapters matching filter criteria.", total_chapters)

        if total_chapters == 0:
            print("No chapters found for the specified filters.")
            return 0

        target_per_level = get_target_distribution(args.target_per_chapter)

        # Dry run display
        if args.dry_run:
            print("\n" + "=" * 80)
            print("VIDYAFLOW PIPELINE — DRY RUN PLAN")
            print("=" * 80)
            for idx, ch in enumerate(chapters, 1):
                b_code = normalize_board_code(ch.subject.board.code)
                cls_num = ch.subject.class_grade.grade_number
                s_name = ch.subject.name

                concept = db.query(Concept).filter(Concept.chapter_id == ch.id).first()
                existing_q = 0
                if concept:
                    existing_q = (
                        db.query(Question)
                        .filter(Question.concept_id == concept.id, Question.review_status != "rejected")
                        .count()
                    )

                existing_mm = (
                    db.query(ChapterMindMap)
                    .filter(ChapterMindMap.chapter_id == ch.id, ChapterMindMap.review_status != "rejected")
                    .first()
                )

                q_status = f"{existing_q}/{args.target_per_chapter} exist"
                if existing_q >= args.target_per_chapter:
                    q_status += " (satisfied)"
                else:
                    q_status += f" (generate {args.target_per_chapter - existing_q})"

                mm_status = "exists" if existing_mm else "needs generation"

                print(
                    f"[{idx:3d}/{total_chapters:3d}] Ch {ch.id:3d}: Class {cls_num} {s_name:<16} "
                    f"({b_code}) - '{ch.title}' | Questions: {q_status} | MindMap: {mm_status}"
                )
            print("=" * 80)
            print(f"Total chapters planned: {total_chapters}. No changes made (dry-run).\n")
            return 0

        # Initialize engines
        gemini_service = GeminiService()
        quiz_engine = QuizEngine(db)

        cumulative_llm_calls = 0
        total_questions_new = 0
        total_mindmaps_new = 0
        total_rejections = 0
        chapter_reports: List[Dict[str, Any]] = []
        pipeline_stopped_reason = "completed"

        print("\n" + "=" * 85)
        print("STARTING VIDYAFLOW CONTENT GENERATION")
        print("=" * 85)

        for idx, ch in enumerate(chapters, 1):
            b_code = normalize_board_code(ch.subject.board.code)
            cls_num = ch.subject.class_grade.grade_number
            s_name = ch.subject.name

            ch_report: Dict[str, Any] = {
                "chapter_id": ch.id,
                "chapter_title": ch.title,
                "board": b_code,
                "class": cls_num,
                "subject": s_name,
                "questions": {},
                "mindmap": {},
                "rejections": [],
                "errors": [],
            }

            q_info = "skipped"
            mm_info = "skipped"

            # Check hard LLM call cap
            if args.max_llm_calls and cumulative_llm_calls >= args.max_llm_calls:
                pipeline_stopped_reason = f"max_llm_calls cap ({args.max_llm_calls}) reached"
                logger.warning(pipeline_stopped_reason)
                break

            # -------------------------------------------------------------
            # Part A: Questions Pool Generation
            # -------------------------------------------------------------
            if args.what in ("questions", "both"):
                concept = db.query(Concept).filter(Concept.chapter_id == ch.id).first()
                if not concept:
                    ensure_chapter_concepts(db)
                    concept = db.query(Concept).filter(Concept.chapter_id == ch.id).first()

                existing_q = 0
                if concept:
                    existing_q = (
                        db.query(Question)
                        .filter(Question.concept_id == concept.id, Question.review_status != "rejected")
                        .count()
                    )

                if existing_q >= args.target_per_chapter and not args.force:
                    q_info = f"{existing_q}/{args.target_per_chapter} (satisfied)"
                    ch_report["questions"] = {"status": "satisfied", "total": existing_q, "new": 0}
                else:
                    max_remaining = None
                    if args.max_llm_calls:
                        max_remaining = max(0, args.max_llm_calls - cumulative_llm_calls)

                    try:
                        q_res = generate_chapter_pool(
                            db=db,
                            chapter=ch,
                            target_per_level=target_per_level,
                            engine=quiz_engine,
                            max_llm_calls_remaining=max_remaining,
                        )
                        calls_made = q_res.get("newly_generated_llm_calls", 0)
                        cumulative_llm_calls += calls_made
                        new_stored = max(0, q_res.get("total_questions", 0) - existing_q)
                        total_questions_new += new_stored
                        total_rejections += len(q_res.get("rejections", []))
                        ch_report["rejections"].extend(q_res.get("rejections", []))

                        ch_report["questions"] = {
                            "status": "generated",
                            "total": q_res.get("total_questions", 0),
                            "new": new_stored,
                            "by_level": q_res.get("questions_by_level", {}),
                            "llm_calls": calls_made,
                        }
                        q_info = f"{q_res.get('total_questions', 0)}/{args.target_per_chapter} ({new_stored} new)"

                        if q_res.get("quota_exhausted"):
                            q_err = q_res.get("quota_error")
                            if q_err and getattr(q_err, "is_daily_exhaustion", False):
                                print(
                                    f"\nDaily quota exhausted after {idx} chapters / "
                                    f"{total_questions_new} questions. Re-run tomorrow; pipeline will resume where it stopped."
                                )
                                pipeline_stopped_reason = "daily_quota_exhausted"
                                chapter_reports.append(ch_report)
                                break
                            elif q_err and getattr(q_err, "retry_after_seconds", None):
                                sleep_sec = min(60, q_err.retry_after_seconds)
                                logger.info("Rate limit hit. Sleeping %d seconds...", sleep_sec)
                                time.sleep(sleep_sec)

                    except GeminiQuotaError as e:
                        if e.is_daily_exhaustion:
                            print(
                                f"\nDaily quota exhausted after {idx} chapters / "
                                f"{total_questions_new} questions. Re-run tomorrow; pipeline will resume where it stopped."
                            )
                            pipeline_stopped_reason = "daily_quota_exhausted"
                            chapter_reports.append(ch_report)
                            break
                        else:
                            sleep_sec = min(60, e.retry_after_seconds or 10)
                            logger.info("Rate limit hit. Sleeping %d seconds...", sleep_sec)
                            time.sleep(sleep_sec)
                    except Exception as e:
                        logger.error("Error generating question pool for chapter %d: %s", ch.id, e)
                        ch_report["errors"].append(str(e))
                        q_info = f"error: {str(e)[:30]}"

            # -------------------------------------------------------------
            # Part B: Mind Map Generation
            # -------------------------------------------------------------
            if args.what in ("mindmaps", "both") and pipeline_stopped_reason == "completed":
                existing_mm = (
                    db.query(ChapterMindMap)
                    .filter(ChapterMindMap.chapter_id == ch.id, ChapterMindMap.review_status != "rejected")
                    .first()
                )

                if existing_mm and not args.force:
                    mm_info = f"exists (grounded={existing_mm.grounded})"
                    ch_report["mindmap"] = {
                        "status": "exists",
                        "grounded": existing_mm.grounded,
                        "branches": len(existing_mm.mindmap_json.get("branches", [])),
                    }
                else:
                    try:
                        mm_res = generate_chapter_mindmap(
                            db=db,
                            chapter=ch,
                            gemini_service=gemini_service,
                            max_retries=3,
                        )
                        calls = mm_res.get("llm_calls", 0)
                        cumulative_llm_calls += calls

                        if mm_res.get("mindmap") is not None:
                            total_mindmaps_new += 1
                            mm_info = f"generated (grounded={mm_res['grounded']})"
                            ch_report["mindmap"] = {
                                "status": "generated",
                                "grounded": mm_res["grounded"],
                                "llm_calls": calls,
                                "branches": len(mm_res["mindmap"].mindmap_json.get("branches", [])),
                            }
                        else:
                            mm_info = f"failed ({mm_res.get('error')})"
                            ch_report["mindmap"] = {"status": "failed", "error": mm_res.get("error")}
                            ch_report["errors"].append(f"MindMap: {mm_res.get('error')}")

                    except GeminiQuotaError as e:
                        if e.is_daily_exhaustion:
                            print(
                                f"\nDaily quota exhausted after {idx} chapters. "
                                "Re-run tomorrow; pipeline will resume where it stopped."
                            )
                            pipeline_stopped_reason = "daily_quota_exhausted"
                            chapter_reports.append(ch_report)
                            break
                        else:
                            sleep_sec = min(60, e.retry_after_seconds or 10)
                            logger.info("Rate limit hit during mindmap. Sleeping %d seconds...", sleep_sec)
                            time.sleep(sleep_sec)
                    except Exception as e:
                        logger.error("Error generating mindmap for chapter %d: %s", ch.id, e)
                        ch_report["errors"].append(str(e))
                        mm_info = f"error: {str(e)[:30]}"

            # Commit after each chapter finishes
            db.commit()
            chapter_reports.append(ch_report)

            # Print chapter progress line
            print(
                f"[{idx:3d}/{total_chapters:3d}] Class {cls_num} {s_name} - {ch.title} ({b_code}) "
                f"-> questions: {q_info}, mindmap: {mm_info}"
            )

        # -------------------------------------------------------------
        # Summary & JSON Report
        # -------------------------------------------------------------
        print("\n" + "=" * 85)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 85)
        print(f"Status:                    {pipeline_stopped_reason}")
        print(f"Total chapters processed:  {len(chapter_reports)}")
        print(f"New questions generated:   {total_questions_new}")
        print(f"New mind maps generated:   {total_mindmaps_new}")
        print(f"Rejections recorded:       {total_rejections}")
        print(f"Total LLM calls made:      {cumulative_llm_calls}")
        print("=" * 85)

        report_payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "status": pipeline_stopped_reason,
            "summary": {
                "chapters_processed": len(chapter_reports),
                "questions_generated": total_questions_new,
                "mindmaps_generated": total_mindmaps_new,
                "rejections_count": total_rejections,
                "llm_calls": cumulative_llm_calls,
            },
            "chapters": chapter_reports,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)

        print(f"Detailed run metrics saved to: {os.path.abspath(report_file)}\n")
        return 0

    except Exception as e:
        logger.exception("Fatal error in content generation pipeline: %s", e)
        return 1
    finally:
        db.close()


def main():
    args = parse_args()
    code = execute_pipeline(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
