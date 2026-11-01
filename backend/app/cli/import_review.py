"""
Import Review CLI.

Imports reviewed CSV back into the VidyaFlow database, updating question review statuses.
Validates 'approved' or 'rejected'.
Idempotent and provides clear summary metrics.
"""

import argparse
import csv
import logging
import sys
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.quiz import Question

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_review")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import reviewed questions back to database")
    parser.add_argument(
        "--file",
        type=str,
        default="review_sample.csv",
        help="Path to edited review CSV file (default: review_sample.csv)",
    )
    return parser.parse_args()


def import_question_reviews(file_path: str) -> int:
    db: Session = SessionLocal()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_rows = len(rows)
        reviewed_count = 0
        approved_count = 0
        rejected_count = 0
        unchanged_count = 0
        invalid_count = 0

        for row in rows:
            raw_qid = row.get("question_id", "").strip()
            new_status = row.get("new_review_status", "").strip().lower()
            rejection_reason = row.get("rejection_reason", "").strip()

            if not raw_qid:
                continue

            try:
                qid = int(raw_qid)
            except ValueError:
                logger.warning("Skipping invalid question_id: %s", raw_qid)
                continue

            q = db.query(Question).filter(Question.id == qid).first()
            if not q:
                logger.warning("Question %d not found in database", qid)
                continue

            if not new_status:
                unchanged_count += 1
                continue

            if new_status not in ("approved", "rejected"):
                logger.warning(
                    "Invalid new_review_status '%s' for question %d. Must be 'approved' or 'rejected'.",
                    new_status,
                    qid,
                )
                invalid_count += 1
                continue

            if q.review_status == new_status:
                unchanged_count += 1
                continue

            # Update status
            q.review_status = new_status
            reviewed_count += 1
            if new_status == "approved":
                approved_count += 1
            elif new_status == "rejected":
                rejected_count += 1
                if rejection_reason:
                    logger.info("Question %d rejected. Reason: %s", qid, rejection_reason)

        db.commit()

        print(
            f"Imported {reviewed_count} reviews: {approved_count} approved, "
            f"{rejected_count} rejected. Unchanged: {unchanged_count}."
        )
        if invalid_count > 0:
            print(f"Skipped {invalid_count} rows with invalid status.")
        return 0

    except FileNotFoundError:
        print(f"Error: Review file '{file_path}' not found.")
        return 1
    except Exception as e:
        logger.exception("Error importing reviews: %s", e)
        return 1
    finally:
        db.close()


def main():
    args = parse_args()
    code = import_question_reviews(args.file)
    sys.exit(code)


if __name__ == "__main__":
    main()
