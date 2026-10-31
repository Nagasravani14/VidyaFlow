import argparse
import sys
from app.database import SessionLocal, Base, engine
from app.importer.pipeline import CurriculumImporter


def main():
    parser = argparse.ArgumentParser(description="Import structured curriculum data into VidyaFlow database.")
    parser.add_argument("file_path", help="Path to JSON or CSV curriculum file")
    args = parser.parse_args()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        importer = CurriculumImporter(db)
        if args.file_path.endswith(".csv"):
            report = importer.import_from_csv(args.file_path)
        else:
            report = importer.import_from_json(args.file_path)

        print("\n" + "=" * 50)
        print("VIDYAFLOW CURRICULUM IMPORT REPORT")
        print("=" * 50)
        print(f"Status:             {'SUCCESS' if report.success else 'FAILED'}")
        print(f"Source File:        {report.source_file}")
        print(f"Boards Created:     {report.boards_created} (Updated: {report.boards_updated})")
        print(f"Subjects Created:   {report.subjects_created} (Updated: {report.subjects_updated})")
        print(f"Chapters Created:   {report.chapters_created} (Updated: {report.chapters_updated})")
        print(f"Topics Created:     {report.topics_created} (Updated: {report.topics_updated})")
        print(f"Learning Obj:       {report.learning_objectives_created}")
        print(f"Lessons Created:    {report.lessons_created}")
        print(f"Worked Examples:    {report.worked_examples_created}")
        print(f"Questions Created:  {report.questions_created} (Options: {report.options_created})")
        print(f"Prerequisites:      {report.prerequisites_created}")
        print(f"Total Imported:     {report.total_imported}")
        print(f"Total Updated:      {report.total_updated}")

        if report.failed_records:
            print(f"\nErrors / Failed Records ({len(report.failed_records)}):")
            for idx, err in enumerate(report.failed_records, 1):
                print(f"  {idx}. {err}")

        print("=" * 50 + "\n")
        if not report.success:
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
