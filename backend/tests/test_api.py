from app.importer.pipeline import CurriculumImporter


def seed_test_curriculum(db_session):
    data = {
        "board": {
            "code": "API_TEST_BOARD",
            "name": "API Test Board",
            "country": "India",
            "state_or_region": "Telangana",
            "is_active": True,
        },
        "syllabus_version": "2024-2025",
        "classes": [
            {
                "grade_number": 10,
                "subjects": [
                    {
                        "code": "API_10_MATH",
                        "name": "Mathematics",
                        "category": "STEM",
                        "description": "Grade 10 Math",
                        "chapters": [
                            {
                                "chapter_number": 1,
                                "code": "API_10_M_CH01",
                                "title": "Real Numbers",
                                "description": "Euclid division lemma and fundamental theorem of arithmetic",
                                "estimated_minutes": 90,
                                "topics": [
                                    {
                                        "topic_code": "API_10_M_T01",
                                        "title": "Fundamental Theorem of Arithmetic",
                                        "description": "Prime factorisation of composite numbers",
                                        "lessons": [
                                            {
                                                "section_type": "explanation",
                                                "title": "Prime Factorisation",
                                                "content": "Every composite number can be expressed as a product of primes uniquely.",
                                                "summary": "Unique factorisation theorem.",
                                            }
                                        ],
                                        "practice_questions": [
                                            {
                                                "question_code": "Q_API_01",
                                                "question_text": "Find HCF of 12 and 18",
                                                "question_type": "multiple_choice",
                                                "difficulty_level": "easy",
                                                "hint": "List common factors",
                                                "worked_explanation": "12 = 2*2*3, 18 = 2*3*3. HCF = 2*3 = 6",
                                                "correct_answer": "6",
                                                "options": [
                                                    {"option_index": 0, "option_text": "2", "is_correct": False},
                                                    {"option_index": 1, "option_text": "6", "is_correct": True},
                                                    {"option_index": 2, "option_text": "12", "is_correct": False},
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    importer = CurriculumImporter(db_session)
    importer.import_from_dict(data)


def test_health_check_endpoints(client):
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "healthy"

    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == "healthy"


def test_list_boards(client, db_session):
    seed_test_curriculum(db_session)

    res = client.get("/api/v1/boards")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    board_codes = [b["code"] for b in data]
    assert "API_TEST_BOARD" in board_codes


def test_list_classes(client, db_session):
    res = client.get("/api/v1/classes")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 5
    assert [c["grade_number"] for c in data] == [6, 7, 8, 9, 10]


def test_list_subjects_and_filters(client, db_session):
    seed_test_curriculum(db_session)

    # Filter by class 10
    res = client.get("/api/v1/subjects?class_grade=10")
    assert res.status_code == 200
    subjects = res.json()
    assert len(subjects) >= 1
    assert subjects[0]["code"] == "API_10_MATH"
    assert subjects[0]["chapter_count"] == 1

    # Filter by class 7 (no subjects seeded)
    res_empty = client.get("/api/v1/subjects?class_grade=7")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0


def test_get_chapter_and_topics(client, db_session):
    seed_test_curriculum(db_session)

    subj_res = client.get("/api/v1/subjects?class_grade=10")
    subj_id = subj_res.json()[0]["id"]

    # List chapters
    ch_list_res = client.get(f"/api/v1/chapters?subject_id={subj_id}")
    assert ch_list_res.status_code == 200
    chapters = ch_list_res.json()
    assert len(chapters) == 1
    ch_id = chapters[0]["id"]

    # Get chapter detail
    ch_detail_res = client.get(f"/api/v1/chapters/{ch_id}")
    assert ch_detail_res.status_code == 200
    ch_detail = ch_detail_res.json()
    assert ch_detail["title"] == "Real Numbers"
    assert len(ch_detail["topics"]) == 1
    topic_id = ch_detail["topics"][0]["id"]

    # Get topic detail with lessons
    topic_res = client.get(f"/api/v1/topics/{topic_id}")
    assert topic_res.status_code == 200
    topic_detail = topic_res.json()
    assert topic_detail["title"] == "Fundamental Theorem of Arithmetic"
    assert len(topic_detail["lessons"]) == 1
    assert topic_detail["lessons"][0]["section_type"] == "explanation"

    # Get topic practice questions
    q_res = client.get(f"/api/v1/topics/{topic_id}/questions")
    assert q_res.status_code == 200
    questions = q_res.json()
    assert len(questions) == 1
    assert questions[0]["question_code"] == "Q_API_01"
    assert len(questions[0]["options"]) == 3


def test_search_curriculum(client, db_session):
    seed_test_curriculum(db_session)

    # Search for "Factorisation"
    res = client.get("/api/v1/search?query=Factorisation")
    assert res.status_code == 200
    search_data = res.json()
    assert search_data["total"] >= 1
    assert any("Factorisation" in item["title"] or "factorisation" in (item["snippet"] or "").lower() for item in search_data["items"])

    # Search for non-existent keyword
    res_none = client.get("/api/v1/search?query=NonExistentKeywordXYZ")
    assert res_none.status_code == 200
    assert res_none.json()["total"] == 0
