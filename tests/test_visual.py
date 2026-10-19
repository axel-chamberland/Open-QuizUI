import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

from backend.build import ACTION_FILE, ACTION_OUTPUT, THEMES, build

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests" / "test_files"
FLASHCARD_DIR = ROOT / "tests" / "test_files_flashcards"


@pytest.fixture(scope="session")
def built_action():
    """Run the full build and load the generated Action class."""

    build(ACTION_FILE, ACTION_OUTPUT)

    assert ACTION_OUTPUT.exists(), f"Build did not produce {ACTION_OUTPUT}"

    spec = importlib.util.spec_from_file_location(
        "built_action_function",
        ACTION_OUTPUT,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules["built_action_function"] = module
    spec.loader.exec_module(module)

    return module.Action


def minimal_body(content: str):
    return {"messages": [{"role": "user", "content": content}]}


def extract_output(result):
    if hasattr(result, "body"):
        body = result.body

        if isinstance(body, memoryview):
            body = body.tobytes()

        return body.decode() if isinstance(body, (bytes, bytearray)) else str(body)

    return str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file", [f for f in os.listdir(TEST_DIR) if f.endswith(".json")]
)
async def test_each_case(file, built_action):
    action = built_action()

    action.valves = built_action().Valves(
        **{
            **action.valves.model_dump(),
            "shuffle_choices": False,
            "enable_mathjax": True,
        }
    )

    path = os.path.join(TEST_DIR, file)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "content" in data, (
        f"The test file, {file}, is missing 'content': {data.keys()}"
    )

    content = data["content"]

    result = await action.action(
        minimal_body(content),
        __event_emitter__=lambda *_a, **_k: None,
        __event_call__=None,
        __user__=None,
    )
    output = extract_output(result)

    assert output is not None
    assert output != ""
    assert "<html" in output.lower()

    if output:
        os.makedirs("tmp", exist_ok=True)
        with open(f"tmp/{file.replace('.json', '.html')}", "w", encoding="utf-8") as f:
            f.write(output)


def extract_payload(output):
    """Pull the quiz payload the page receives out of the built HTML."""
    match = re.search(
        r'<script id="app-data" type="application/json">(.*?)</script>',
        output,
        re.S,
    )

    assert match is not None, "The built page has no app-data payload."

    return json.loads(match.group(1))


def flashcards_valves(built_action, **overrides):
    action = built_action()

    action.valves = built_action().Valves(
        **{
            **action.valves.model_dump(),
            "shuffle_choices": False,
            "enable_mathjax": True,
            **overrides,
        }
    )

    return action


async def action_output(action, body):
    result = await action.action(
        body,
        __event_emitter__=lambda *_a, **_k: None,
        __event_call__=None,
        __user__=None,
    )

    return extract_output(result)


def error_emitter():
    """An event emitter that records the notifications it receives."""
    notifications = []

    async def emitter(event):
        notifications.append(event)

    return notifications, emitter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file", [f for f in os.listdir(FLASHCARD_DIR) if f.endswith(".json")]
)
async def test_flashcard_case(file, built_action):
    """Auto parsing serves flashcards when the message holds no choices."""

    with open(FLASHCARD_DIR / file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "content" in data, (
        f"The test file, {file}, is missing 'content': {data.keys()}"
    )

    assert "expected" in data, (
        f"The test file, {file}, is missing 'expected' field: {data.keys()}"
    )

    output = await action_output(
        flashcards_valves(built_action), minimal_body(data["content"])
    )

    assert output is not None
    assert output != ""
    assert "<html" in output.lower()

    payload = extract_payload(output)

    quiz = {
        "title": data["expected"][0],
        "questions": data["expected"][1],
    }

    assert payload["quiz"] == quiz

    for question in payload["quiz"]["questions"]:
        # A flashcard carries its answer as the only option.
        assert len(question["options"]) == 1

    os.makedirs("tmp", exist_ok=True)
    with open(f"tmp/{file.replace('.json', '.html')}", "w", encoding="utf-8") as f:
        f.write(output)


@pytest.mark.asyncio
async def test_forcing_flashcards_on_a_multiple_choice_quiz(built_action):
    """Forcing flashcards shows a quiz with choices as cards."""

    with open(TEST_DIR / "Feature_Showcase.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "expected" in data, (
        f"The test file is missing 'expected' field: {data.keys()}"
    )

    output = await action_output(
        flashcards_valves(built_action, parse_mode="flashcards"),
        minimal_body(data["content"]),
    )

    assert "<html" in output.lower()

    questions = extract_payload(output)["quiz"]["questions"]
    expected = data["expected"][1]

    assert len(questions) == len(expected)

    for question, choice_question in zip(questions, expected):
        # The correct choice becomes the card's answer.
        answer = choice_question["options"][choice_question["correct_index"]]

        assert question["options"] == [answer]
        assert question["correct_index"] == 0


@pytest.mark.asyncio
async def test_forcing_multiple_choice_on_flashcards(built_action):
    """Forcing a quiz with choices refuses a flashcard message."""

    with open(FLASHCARD_DIR / "Flashcards_bare_heading.json", "r", encoding="utf-8") as f:
        content = json.load(f)["content"]

    notifications, emitter = error_emitter()

    result = await flashcards_valves(
        built_action, parse_mode="multiple-choice questions"
    ).action(
        minimal_body(content),
        __event_emitter__=emitter,
        __event_call__=None,
        __user__=None,
    )

    assert "html" not in extract_output(result).lower()

    assert notifications[-1]["data"]["type"] == "error"

    message = notifications[-1]["data"]["content"]

    assert "no valid questions were parsed" in message
    # The questions the parser turned down are reported one by one.
    assert "Line 1: question has only 0 option(s) (need >= 2)." in message


@pytest.mark.asyncio
async def test_flashcard_format_valve_reaches_the_parser(built_action):
    """The flashcard format valve picks which part of the message is read."""

    with open(
        FLASHCARD_DIR / "Flashcards_table_two_columns.json", "r", encoding="utf-8"
    ) as f:
        content = json.load(f)["content"]

    notifications, emitter = error_emitter()

    # Auto would have read the table; forcing question labels finds none.
    result = await flashcards_valves(
        built_action, flashcard_format="question labels"
    ).action(
        minimal_body(content),
        __event_emitter__=emitter,
        __event_call__=None,
        __user__=None,
    )

    assert "html" not in extract_output(result).lower()
    assert "No flashcards were parsed either" in notifications[-1]["data"]["content"]


@pytest.mark.asyncio
async def test_unreadable_message_reports_both_parsers(built_action):
    """A message that is neither format says why neither one parsed."""

    notifications, emitter = error_emitter()

    result = await flashcards_valves(built_action).action(
        minimal_body("Just some prose, with no quiz in it."),
        __event_emitter__=emitter,
        __event_call__=None,
        __user__=None,
    )

    assert "html" not in extract_output(result).lower()

    message = notifications[-1]["data"]["content"]

    assert "no valid questions were parsed" in message
    assert "No flashcards were parsed either" in message


QUIZ_MESSAGE = """### Capital cities

**1. What is the capital of France?**

A) Lyon
B) Paris
C) Marseille

**Answer:** B

**2. What is the capital of Italy?**

A) Rome
B) Milan
C) Turin

**Answer:** A
"""


async def run_action(built_action, __user__, **admin_valves):
    """Run the action on the sample quiz, and read its page payload."""

    action = built_action()
    action.valves = built_action.Valves(**admin_valves)

    result = await action.action(
        minimal_body(QUIZ_MESSAGE),
        __event_emitter__=lambda *_a, **_k: None,
        __event_call__=None,
        __user__=__user__,
    )

    return extract_payload(extract_output(result))


def test_user_valves_are_all_admin_valves(built_action):
    """Every user valve is one the admin's Valves also holds.

    effective_valves copies the user's values onto a Valves instance, so
    a field that only UserValves holds would be set there without ever
    reaching the quiz.
    """

    assert set(built_action.UserValves.model_fields) <= set(
        built_action.Valves.model_fields
    )


@pytest.mark.asyncio
async def test_user_valves_override_the_admin_ones(built_action):
    """The settings a user saved are the ones their page runs with."""

    payload = await run_action(
        built_action,
        quiz_mode="multiple-choice questions",
        enable_mathjax=True,
        request_retention=0.9,
        spaced_repetition_queue_size=20,
        __user__={
            "valves": built_action.UserValves(
                quiz_mode="flashcards",
                enable_mathjax=False,
                enable_spaced_repetition=True,
                request_retention=0.75,
                spaced_repetition_queue_size=5,
            )
        },
    )

    assert payload["mode"] == "flashcard"
    assert payload["enableMathJax"] is False
    assert payload["srsOnLoad"] is True
    assert payload["requestRetention"] == 0.75
    assert payload["srsQueueSize"] == 5


@pytest.mark.asyncio
async def test_user_valves_leave_the_rest_to_the_admin(built_action):
    """A field the user never set keeps following the admin's valve."""

    payload = await run_action(
        built_action,
        quiz_mode="flashcards",
        enable_mathjax=True,
        request_retention=0.8,
        spaced_repetition_queue_size=7,
        # This user only ever changed the theme.
        __user__={"valves": built_action.UserValves(theme_mode="dark")},
    )

    assert payload["mode"] == "flashcard"
    assert payload["enableMathJax"] is True
    assert payload["requestRetention"] == 0.8
    assert payload["srsQueueSize"] == 7


@pytest.mark.asyncio
async def test_user_without_saved_valves_gets_the_admin_ones(built_action):
    """A user who never opened the panel runs on the admin's valves."""

    payload = await run_action(
        built_action,
        quiz_mode="flashcards",
        enable_mathjax=True,
        __user__={"id": "a-user-id"},
    )

    assert payload["mode"] == "flashcard"
    assert payload["enableMathJax"] is True


@pytest.mark.asyncio
async def test_user_theme_reaches_the_page(built_action):
    """The theme a user picked is the one their page is built with."""

    action = built_action()
    action.valves = action.Valves(dark_theme="default_dark")

    result = await action.action(
        minimal_body(QUIZ_MESSAGE),
        __event_emitter__=lambda *_a, **_k: None,
        __event_call__=None,
        __user__={
            "valves": built_action.UserValves(
                theme_mode="dark", dark_theme="tokyonight"
            )
        },
    )

    assert THEMES["tokyonight"] in extract_output(result)
