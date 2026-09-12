import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


QUIZ = {
    "title": "Test Quiz",
    "questions": [
        {
            "question": "What is 2 + 2?",
            "answer": "4",
            "distractors": ["3", "5"],
            "explanation": "2 + 2 equals 4.",
        },
        {
            "question": "What is the capital of France?",
            "answer": "Paris",
            "distractors": ["London", "Berlin"],
            "explanation": "Paris is the capital of France.",
        },
        {
            "question": "Which number is even?",
            "answer": "8",
            "distractors": ["3", "5"],
            "explanation": "8 is even.",
        },
    ],
}


@pytest.fixture(scope="session")
def frontend_server():
    """Serve the real frontend so native ES module imports work."""
    handler = partial(SimpleHTTPRequestHandler, directory=FRONTEND)

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{server.server_port}"

    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def page():
    """Create a synchronous Playwright page."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(3000)

        yield page

        browser.close()


@pytest.fixture
def page_with_quiz(page: Page, frontend_server):
    """
    Load the real frontend with deterministic test data.

    The HTML and ES modules come directly from frontend/.
    Only the app-data payload is replaced for the test.
    """
    app_data = json.dumps(
        {
            "enableMathJax": False,
            "quiz": QUIZ,
        },
        ensure_ascii=False,
    )

    def handle_index(route):
        html = (FRONTEND / "index.html").read_text()

        html = re.sub(
            r'<script id="app-data" type="application/json">.*?</script>',
            f'<script id="app-data" type="application/json">{app_data}</script>',
            html,
            flags=re.DOTALL,
        )

        route.fulfill(
            status=200,
            content_type="text/html",
            body=html,
        )

    page.route("**/index.html", handle_index)

    page.goto(f"{frontend_server}/index.html")

    # Wait until the frontend has rendered the choices.
    page.locator("#options button").first.wait_for()

    return page


def option(page: Page, index: int):
    """Return an option button by zero-based position."""
    return page.locator("#options button").nth(index)


def next_question(page: Page):
    """Advance to the next question."""
    page.locator("#next-button").click()


def reveal_answer(page: Page):
    """Reveal the answer to the current question."""
    page.locator("#reveal-button").click()


def test_quiz_renders(page_with_quiz):
    """The frontend initializes the quiz correctly."""
    page = page_with_quiz

    assert page.locator("#title").inner_text() == "Test Quiz"
    assert page.locator("#question").inner_text() == "What is 2 + 2?"
    assert page.locator("#question-count").inner_text() == "3"
    assert page.locator("#question-number").input_value() == "1"
    assert page.locator("#options button").count() == 3


def test_correct_answer_is_recorded(page_with_quiz):
    """Selecting the correct answer marks it correct and disables the options."""
    page = page_with_quiz

    option(page, 1).click()

    assert "correct" in (option(page, 1).get_attribute("class") or "")

    assert all(page.locator("#options button").nth(i).is_disabled() for i in range(3))


def test_first_wrong_answer_remains_wrong_after_reveal(page_with_quiz):
    """
    The first submitted wrong answer remains the recorded answer
    after the correct answer is revealed.
    """
    page = page_with_quiz

    option(page, 0).click()

    assert "wrong" in (option(page, 0).get_attribute("class") or "")

    reveal_answer(page)

    next_question(page)
    option(page, 1).click()

    next_question(page)
    reveal_answer(page)
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#correct").inner_text()
    assert "1" in page.locator("#wrong").inner_text()
    assert "1" in page.locator("#skipped").inner_text()

    correction = page.locator("#question-corrections").inner_text()
    assert "3" in correction


def test_multiple_wrong_answers_keep_first_answer(page_with_quiz):
    """
    Multiple wrong attempts on a question do not replace the first
    submitted answer in the correction.
    """
    page = page_with_quiz

    option(page, 0).click()
    option(page, 2).click()

    reveal_answer(page)
    next_question(page)

    option(page, 1).click()
    next_question(page)

    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#wrong").inner_text()

    correction = page.locator("#question-corrections").inner_text()
    assert "3" in correction


def test_revealing_unanswered_question_marks_it_skipped(page_with_quiz):
    """Revealing an unanswered question records it as skipped."""
    page = page_with_quiz

    reveal_answer(page)
    next_question(page)

    option(page, 1).click()
    next_question(page)

    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#skipped").inner_text()
    assert "0" in page.locator("#unanswered").inner_text()

    correction = page.locator("#question-corrections").inner_text()
    assert "Skipped" in correction


def test_next_without_answering_remains_unanswered(page_with_quiz):
    """Moving past a question without answering leaves it unanswered."""
    page = page_with_quiz

    next_question(page)

    option(page, 1).click()
    next_question(page)

    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#unanswered").inner_text()
    assert "0" in page.locator("#skipped").inner_text()


def test_results_use_first_attempts(page_with_quiz):
    """Final results reflect the original outcome of each question."""
    page = page_with_quiz

    option(page, 0).click()
    next_question(page)

    option(page, 1).click()
    next_question(page)

    reveal_answer(page)
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#correct").inner_text()
    assert "1" in page.locator("#wrong").inner_text()
    assert "1" in page.locator("#skipped").inner_text()
    assert "0" in page.locator("#unanswered").inner_text()


def test_restart_resets_quiz(page_with_quiz):
    """Restarting the quiz returns it to its initial state."""
    page = page_with_quiz

    option(page, 1).click()
    next_question(page)

    assert page.locator("#question").inner_text() == ("What is the capital of France?")

    option(page, 1).click()
    next_question(page)

    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    page.get_by_role("button", name="Restart Quiz").click()

    confirmation = page.locator("#restart-confirm")
    assert confirmation.is_visible()

    confirmation.get_by_role("button", name="Confirm restart").click()

    assert page.locator("#question").inner_text() == "What is 2 + 2?"
    assert page.locator("#question-number").input_value() == "1"

    assert all(
        not page.locator("#options button").nth(i).is_disabled() for i in range(3)
    )


def test_editor_opens(page_with_quiz):
    """The question editor can be opened from the quiz."""
    page = page_with_quiz

    page.locator("#editor-button").click()

    assert page.locator("#editor").is_visible()
    assert page.locator("#editor-question").is_visible()
    assert page.locator("#editor-answer-number").is_visible()
    assert page.locator("#editor-distractors").is_visible()


def test_exhausting_wrong_answers_reveals_correct_answer(page_with_quiz):
    """Selecting every wrong answer automatically reveals the correct answer."""
    page = page_with_quiz

    option(page, 0).click()
    option(page, 2).click()

    assert "correct" in (option(page, 1).get_attribute("class") or "")
    assert page.locator("#explanation").is_visible()

    next_question(page)
    option(page, 1).click()

    next_question(page)
    option(page, 2).click()

    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#wrong").inner_text()
    assert "2" in page.locator("#correct").inner_text()
    assert "0" in page.locator("#skipped").inner_text()


def test_question_number_navigation_clamps_to_valid_range(page_with_quiz):
    """Direct question navigation clamps invalid question numbers."""
    page = page_with_quiz

    page.locator("#question-number").fill("3")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "3"
    assert page.locator("#question").inner_text() == "Which number is even?"

    page.locator("#question-number").fill("999")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "3"

    page.locator("#question-number").fill("0")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "1"
    assert page.locator("#question").inner_text() == "What is 2 + 2?"


def test_keyboard_controls(page_with_quiz):
    """Keyboard shortcuts answer questions and navigate the quiz."""
    page = page_with_quiz

    page.keyboard.press("2")

    assert "correct" in (option(page, 1).get_attribute("class") or "")

    page.keyboard.press("Enter")

    assert page.locator("#question-number").input_value() == "2"
    assert page.locator("#question").inner_text() == ("What is the capital of France?")

    page.keyboard.press("ArrowRight")

    assert page.locator("#question-number").input_value() == "3"

    page.keyboard.press("ArrowLeft")

    assert page.locator("#question-number").input_value() == "2"

    page.keyboard.press("l")

    assert page.locator("#question-number").input_value() == "3"

    page.keyboard.press("h")

    assert page.locator("#question-number").input_value() == "2"


def test_editor_saves_question_changes(page_with_quiz):
    """Saving the editor updates the question displayed by the quiz."""
    page = page_with_quiz

    page.locator("#editor-button").click()

    page.locator("#editor-question textarea").fill("What is 10 + 10?")
    page.locator("#editor-answer-number").fill("3")

    options = page.locator("#editor-distractors textarea")
    options.nth(0).fill("19")
    options.nth(1).fill("21")
    options.nth(2).fill("20")

    page.locator("#editor-explanation textarea").fill("10 + 10 equals 20.")

    # ES module functions are not globals anymore, so interact with
    # the actual editor UI rather than calling saveEdit() through evaluate().
    page.get_by_role("button", name=re.compile(r"save", re.I)).click()

    # Close the editor through its UI.
    page.get_by_role("button", name=re.compile(r"close", re.I)).click()

    assert page.locator("#question").inner_text() == "What is 10 + 10?"

    options = page.locator("#options button")
    assert options.count() == 3
    assert options.nth(0).inner_text() == "19"
    assert options.nth(1).inner_text() == "21"
    assert options.nth(2).inner_text() == "20"

    options.nth(2).click()

    assert "correct" in (options.nth(2).get_attribute("class") or "")
