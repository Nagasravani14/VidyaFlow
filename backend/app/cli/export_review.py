"""
Export Review CLI.

Exports a random sample of unreviewed AI questions to a CSV file for SME review.
Columns:
question_id, chapter_id, chapter_title, level, question_type, stem, options,
correct_answer, distractor_misconceptions, source, review_status,
new_review_status, rejection_reason
"""

import argparse
import csv
import json
import logging
import random
import sys
from typing import Any, List
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.curriculum import Chapter
from app.models.quiz import Concept, Question
from app.services.concept_mapper import normalize_board_code

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_review")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export AI questions for SME review")
    parser.add_argument(
        "--sample-fraction",
        type=float,
        default=0.10,
        help="Fraction of unreviewed questions to sample (default: 0.10)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of questions to export (default: None)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="review_sample.csv",
        help="Output CSV file path (default: review_sample.csv)",
    )
    parser.add_argument(
        "--board",
        type=str,
        default="all",
        help="Board filter: TS | ICSE | all (default: all)",
    )
    return parser.parse_args()


def export_questions_for_review(args: argparse.Namespace) -> int:
    db: Session = SessionLocal()
    try:
        query = (
            db.query(Question, Concept, Chapter)
            .join(Concept, Question.concept_id == Concept.id)
            .outerjoin(Chapter, Concept.chapter_id == Chapter.id)
            .filter(
                Question.source == "ai",
                Question.review_status == "unreviewed",
            )
        )

        if args.board.lower() != "all":
            b_norm = normalize_board_code(args.board)
            query = query.filter(Concept.board == b_norm)

        all_unreviewed = query.all()
        total_found = len(all_unreviewed)
        logger.info("Found %d unreviewed AI questions.", total_found)

        if total_found == 0:
            print("No unreviewed AI questions found matching the criteria.")
            return 0

        # Sample
        sample_size = max(1, int(round(total_found * args.sample_fraction)))
        if args.limit:
            sample_size = min(sample_size, args.limit)
        sample_size = min(sample_size, total_found)

        rng = random.Random()
        sampled = rng.sample(all_unreviewed, sample_size)
        logger.info("Sampled %d questions for review.", len(sampled))

        fieldnames = [
            "question_id",
            "chapter_id",
            "chapter_title",
            "level",
            "question_type",
            "stem",
            "options",
            "correct_answer",
            "distractor_misconceptions",
            "source",
            "review_status",
            "new_review_status",
            "rejection_reason",
        ]

        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for q, concept, chapter in sampled:
                ch_id = chapter.id if chapter else (concept.chapter_id or "")
                ch_title = chapter.title if chapter else concept.name

                opts_str = json.dumps(q.options, ensure_ascii=False) if q.options else ""
                ans_str = json.dumps(q.correct_answer, ensure_ascii=False) if isinstance(q.correct_answer, (dict, list)) else str(q.correct_answer or "")
                misc_str = json.dumps(q.distractor_misconceptions, ensure_ascii=False) if q.distractor_misconceptions else ""

                writer.writerow({
                    "question_id": q.id,
                    "chapter_id": ch_id,
                    "chapter_title": ch_title,
                    "level": q.level,
                    "question_type": q.question_type,
                    "stem": q.stem,
                    "options": opts_str,
                    "correct_answer": ans_str,
                    "distractor_misconceptions": misc_str,
                    "source": q.source,
                    "review_status": q.review_status or "unreviewed",
                    "new_review_status": "",
                    "rejection_reason": "",
                })

        print(f"\nExported {len(sampled)} unreviewed AI questions to '{args.output}'.")
        print("SME Instructions: Enter 'approved' or 'rejected' in 'new_review_status' column.")
        print(f"Then re-import using: python -m app.cli.import_review --file {args.output}\n")
        return 0

    except Exception as e:
        logger.exception("Error exporting review sample: %s", e)
        return 1
    finally:
        db.close()


def main():
    args = parse_args()
    code = export_questions_for_review(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
