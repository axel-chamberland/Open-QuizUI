import difflib
import json
import os

import pytest

from backend.quiz_function import (
    NoQuestionsFound,
    clean_message,
    flashcards_from_questions,
    parse_flashcards,
    parse_quiz,
)

TEST_DIR = "tests/test_files_flashcards"


def load_case(file):
    """Read one fixture and return its content and expected output."""
    with open(os.path.join(TEST_DIR, file), "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "content" in data, (
        f"The test file, {file}, is missing 'content': {data.keys()}"
    )

    assert "expected" in data, (
        f"The test file, {file}, is missing 'expected' field: {data.keys()}"
    )

    return data["content"], data["expected"]


@pytest.mark.parametrize(
    "file", [f for f in os.listdir(TEST_DIR) if f.endswith(".json")]
)
def test_each_case(file):

    content, expected = load_case(file)

    output: tuple[str, list[dict]] = parse_flashcards(
        clean_message(content, True, True), True
    )

    os.makedirs("tmp", exist_ok=True)
    with open(f"tmp/{file.replace('.json', '.out')}", "w") as f:
        f.write(json.dumps({"expected": output}))

    assert output[0] == expected[0], (
        f"Different title received in {file}. "
        f"This may not be a bad thing: verify the title."
    )

    assert_json_equal(expected[1], output[1], file)


@pytest.mark.parametrize(
    "flashcard_format, expected",
    [
        # A table is the clearer signal, so it wins unless told otherwise.
        ("auto", ["<p>Capital of France?</p>", "<p>Capital of Japan?</p>"]),
        ("table", ["<p>Capital of France?</p>", "<p>Capital of Japan?</p>"]),
        ("question labels", ["<p>Which planet has the largest diameter?</p>"]),
    ],
)
def test_flashcard_format_chooses_the_parser(flashcard_format, expected):
    content = """## Question 1: Which planet has the largest diameter?

Jupiter

| Question | Answer |
| --- | --- |
| Capital of France? | Paris |
| Capital of Japan? | Tokyo |
"""

    _, questions = parse_flashcards(
        clean_message(content, True, True),
        True,
        flashcard_format=flashcard_format,
    )

    assert [question["question"] for question in questions] == expected


def test_forced_flashcard_format_does_not_fall_back():
    content = """## Question 1: Capital of France?

Paris
"""

    with pytest.raises(NoQuestionsFound):
        parse_flashcards(
            clean_message(content, True, True), True, flashcard_format="table"
        )


def test_explanations_disabled():
    content, expected = load_case("Flashcards_unlabelled_paragraphs.json")

    _, questions = parse_flashcards(clean_message(content, True, True), False)

    assert questions[0]["options"] == ["<p>Jupiter</p>"]
    assert all("explanation" not in question for question in questions)


def test_question_without_answer_is_skipped():
    content = """## Question 1: Capital of France?
"""

    with pytest.raises(NoQuestionsFound):
        parse_flashcards(clean_message(content, True, True), True)


def test_multiple_choice_parser_rejects_flashcards():
    content, _ = load_case("Flashcards_unlabelled_paragraphs.json")

    with pytest.raises(NoQuestionsFound):
        parse_quiz(clean_message(content, True, True), True)


def test_flashcards_from_questions():
    questions = [
        {
            "question": "<p>Which planet has the largest diameter?</p>",
            "options": ["<p>Earth</p>", "<p>Jupiter</p>", "<p>Neptune</p>"],
            "correct_index": 1,
            "explanation": "<p>About 139,820 km across.</p>",
        }
    ]

    assert flashcards_from_questions(questions) == [
        {
            "question": "<p>Which planet has the largest diameter?</p>",
            "options": ["<p>Jupiter</p>"],
            "correct_index": 0,
            "explanation": "<p>About 139,820 km across.</p>",
        }
    ]


def assert_json_equal(expected, actual, file):
    expected_json = json.dumps(
        expected, ensure_ascii=False, indent=2, sort_keys=True
    ).splitlines()
    actual_json = json.dumps(
        actual, ensure_ascii=False, indent=2, sort_keys=True
    ).splitlines()

    diff = "\n".join(
        difflib.unified_diff(
            expected_json,
            actual_json,
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )

    assert expected == actual, f"Different questions in {file}:\n\n{diff}"
