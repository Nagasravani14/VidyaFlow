from typing import Any, Dict, List, Tuple


class ValidationError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or [message]


def validate_curriculum_payload(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a structured curriculum dictionary.
    Returns (is_valid, list_of_error_strings).
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["Payload must be a JSON object"]

    # Board validation
    board = data.get("board")
    if not board or not isinstance(board, dict):
        errors.append("Missing or invalid 'board' object")
    else:
        if not board.get("code"):
            errors.append("Board must have a non-empty 'code'")
        if not board.get("name"):
            errors.append("Board must have a non-empty 'name'")

    # Classes validation
    classes = data.get("classes", [])
    if not isinstance(classes, list) or len(classes) == 0:
        errors.append("'classes' must be a non-empty list of class curriculum entries")
    else:
        for idx, cls_entry in enumerate(classes):
            prefix = f"classes[{idx}]"
            grade = cls_entry.get("grade_number")
            if grade is None or not isinstance(grade, int) or grade < 6 or grade > 10:
                errors.append(f"{prefix}: 'grade_number' must be an integer between 6 and 10")

            subjects = cls_entry.get("subjects", [])
            if not isinstance(subjects, list):
                errors.append(f"{prefix}: 'subjects' must be a list")
                continue

            # Check intra-file subject uniqueness
            seen_subject_names = set()
            for s_idx, subj in enumerate(subjects):
                s_prefix = f"{prefix}.subjects[{s_idx}]"
                s_name = subj.get("name")
                s_code = subj.get("code")

                if not s_name:
                    errors.append(f"{s_prefix}: Missing 'name'")
                elif s_name in seen_subject_names:
                    errors.append(f"{s_prefix}: Duplicate subject name '{s_name}' within class {grade}")
                else:
                    seen_subject_names.add(s_name)

                if not s_code:
                    errors.append(f"{s_prefix}: Missing 'code'")

                chapters = subj.get("chapters", [])
                if not isinstance(chapters, list):
                    errors.append(f"{s_prefix}: 'chapters' must be a list")
                    continue

                # Check intra-file chapter uniqueness
                seen_ch_nums = set()
                seen_ch_codes = set()
                for ch_idx, ch in enumerate(chapters):
                    ch_prefix = f"{s_prefix}.chapters[{ch_idx}]"
                    ch_num = ch.get("chapter_number")
                    ch_code = ch.get("code")
                    ch_title = ch.get("title")

                    if ch_num is None or not isinstance(ch_num, int):
                        errors.append(f"{ch_prefix}: 'chapter_number' must be an integer")
                    elif ch_num in seen_ch_nums:
                        errors.append(f"{ch_prefix}: Duplicate chapter_number '{ch_num}' in subject '{s_name}'")
                    else:
                        seen_ch_nums.add(ch_num)

                    if not ch_code:
                        errors.append(f"{ch_prefix}: Missing 'code'")
                    elif ch_code in seen_ch_codes:
                        errors.append(f"{ch_prefix}: Duplicate chapter code '{ch_code}' in subject '{s_name}'")
                    else:
                        seen_ch_codes.add(ch_code)

                    if not ch_title:
                        errors.append(f"{ch_prefix}: Missing 'title'")

                    # Validate topics if present
                    topics = ch.get("topics", [])
                    seen_t_codes = set()
                    for t_idx, topic in enumerate(topics):
                        t_prefix = f"{ch_prefix}.topics[{t_idx}]"
                        t_code = topic.get("topic_code")
                        t_title = topic.get("title")

                        if not t_code:
                            errors.append(f"{t_prefix}: Missing 'topic_code'")
                        elif t_code in seen_t_codes:
                            errors.append(f"{t_prefix}: Duplicate topic_code '{t_code}' in chapter '{ch_title}'")
                        else:
                            seen_t_codes.add(t_code)

                        if not t_title:
                            errors.append(f"{t_prefix}: Missing 'title'")

    return len(errors) == 0, errors
