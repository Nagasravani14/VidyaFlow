import os
import sys

# Configure UTF-8 stdout if possible on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.database import SessionLocal, Base, engine
from app.importer.pipeline import CurriculumImporter


def seed_database():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        importer = CurriculumImporter(db)
        importer.ensure_class_grades()
        print("[OK] Class grades 6-10 initialized.")

        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

        files_to_seed = [
            ("Telangana State Board Verified Syllabus", os.path.join(data_dir, "verified_curriculum_telangana.json")),
            ("ICSE Verified Syllabus", os.path.join(data_dir, "verified_curriculum_icse.json")),
            ("Sample Deep Curriculum Test Fixture", os.path.join(data_dir, "sample_curriculum_import.json")),
        ]

        for label, file_path in files_to_seed:
            if os.path.exists(file_path):
                print(f"\nImporting {label} from {os.path.basename(file_path)}...")
                report = importer.import_from_json(file_path)
                if report.success:
                    print(f"  [OK] Success! Chapters created/updated: {report.chapters_created}/{report.chapters_updated}, Topics: {report.topics_created}")
                else:
                    print(f"  [FAIL] Failed: {report.failed_records}")
            else:
                print(f"  [WARN] Warning: {file_path} not found.")

        print("\n[OK] Database seeding completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

