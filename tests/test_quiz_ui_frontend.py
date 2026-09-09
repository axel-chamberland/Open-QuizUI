import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from playwright.sync_api import Page, sync_playwright

from openquizui.quiz_function import Action

# A small deterministic quiz used to exercise the frontend state machine.
# Choice shuffling is disabled in the fixture so the option positions are
# predictable in the tests.
QUIZ = """\
# Test Quiz

Question 1: What is 2 + 2?

A. 3
B. 4
C. 5

Question 2: What is the capital of France?

A. London
B. Paris
C. Berlin

Question 3: Which number is even?

A. 3
B. 5
C. 8

# Answer key

| Question | Correct Answer | Explanation |
| --- | --- | --- |
| 1 | B | 2 + 2 equals 4. |
| 2 | B | Paris is the capital of France. |
| 3 | C | 8 is even. |
"""


@pytest.fixture
def page():
    """Create a synchronous Playwright page for frontend tests."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(5000)

        yield page

        browser.close()


def generate_quiz_html():
    """
    Generate quiz HTML using the real Action.

    Action.action() is asynchronous, while these frontend tests use
    Playwright's synchronous API. Running the coroutine in a dedicated
    thread gives it its own event loop and avoids conflicting with
    pytest-playwright's event-loop handling.
    """
    action = Action()

    # Make option positions deterministic for the tests.
    action.valves.shuffle_choices = False
    action.valves.enable_mathjax = False

    async def emit(*_args, **_kwargs):
        """No-op event emitter for tests."""
        pass

    async def generate():
        return await action.action(
            {"messages": [{"content": QUIZ}]},
            emit,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(asyncio.run, generate()).result()

    assert hasattr(response, "body")
    return response.body.decode()


@pytest.fixture
def quiz_html():
    """Generate the actual HTML returned by the Action."""
    return generate_quiz_html()


@pytest.fixture
def page_with_quiz(page: Page, quiz_html):
    """Load generated quiz HTML into a Playwright page."""
    page.set_content(quiz_html)

    # Wait until the frontend has rendered the choices.
    page.locator("#options button").first.wait_for()

    return page


def option(page: Page, index: int):
    """Return an option button by its zero-based position."""
    return page.locator("#options button").nth(index)


def next_question(page: Page):
    """Advance to the next question."""
    page.locator("#next-button").click()


def reveal_answer(page: Page):
    """Reveal the answer to the current question."""
    page.locator("#reveal-button").click()


def test_quiz_renders(page_with_quiz):
    """The generated HTML initializes the quiz correctly."""
    page = page_with_quiz

    assert page.locator("#title").inner_text() == "Test Quiz"
    assert page.locator("#question").inner_text() == "What is 2 + 2?"
    assert page.locator("#question-count").inner_text() == "3"
    assert page.locator("#question-number").input_value() == "1"
    assert page.locator("#options button").count() == 3


def test_correct_answer_is_recorded(page_with_quiz):
    """Selecting the correct answer marks it correct and disables the options."""
    page = page_with_quiz

    # Question 1: B is correct.
    option(page, 1).click()

    assert "correct" in (option(page, 1).get_attribute("class") or "")

    # A correct answer ends the question.
    assert all(page.locator("#options button").nth(i).is_disabled() for i in range(3))


def test_first_wrong_answer_remains_wrong_after_reveal(page_with_quiz):
    """
    The first submitted wrong answer remains the recorded answer after
    the correct answer is revealed.
    """
    page = page_with_quiz

    # Question 1: first answer is A (3), which is wrong.
    option(page, 0).click()

    assert "wrong" in (option(page, 0).get_attribute("class") or "")

    # Reveal the correct answer.
    reveal_answer(page)

    # Question 2: answer correctly.
    next_question(page)
    option(page, 1).click()

    # Question 3: reveal without answering.
    next_question(page)
    reveal_answer(page)
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#correct").inner_text()
    assert "1" in page.locator("#wrong").inner_text()
    assert "1" in page.locator("#skipped").inner_text()

    # The correction sheet should retain the first answer, 3.
    correction = page.locator("#question-corrections").inner_text()
    assert "3" in correction


def test_multiple_wrong_answers_keep_first_answer(page_with_quiz):
    """
    Multiple wrong attempts on a question do not replace the first
    submitted answer in the correction.
    """
    page = page_with_quiz

    # Question 1:
    # A = 3 is the first wrong answer.
    # C = 5 is another wrong answer.
    option(page, 0).click()
    option(page, 2).click()

    reveal_answer(page)
    next_question(page)

    # Question 2: correct.
    option(page, 1).click()
    next_question(page)

    # Question 3: correct.
    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#wrong").inner_text()

    # The first answer must remain the recorded answer.
    correction = page.locator("#question-corrections").inner_text()
    assert "3" in correction


def test_revealing_unanswered_question_marks_it_skipped(page_with_quiz):
    """Revealing an unanswered question records it as skipped."""
    page = page_with_quiz

    # Question 1: reveal without selecting an answer.
    reveal_answer(page)
    next_question(page)

    # Question 2: correct.
    option(page, 1).click()
    next_question(page)

    # Question 3: correct.
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

    # Question 1: move on without answering or revealing.
    next_question(page)

    # Question 2: correct.
    option(page, 1).click()
    next_question(page)

    # Question 3: correct.
    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    assert "1" in page.locator("#unanswered").inner_text()
    assert "0" in page.locator("#skipped").inner_text()


def test_results_use_first_attempts(page_with_quiz):
    """
    The final results reflect the original outcome of each question.
    """
    page = page_with_quiz

    # Question 1: wrong.
    option(page, 0).click()
    next_question(page)

    # Question 2: correct.
    option(page, 1).click()
    next_question(page)

    # Question 3: skipped.
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

    # Answer Question 1 and move to Question 2.
    option(page, 1).click()
    next_question(page)

    assert page.locator("#question").inner_text() == ("What is the capital of France?")

    # Finish Question 2 and Question 3 to reach the results screen.
    option(page, 1).click()
    next_question(page)

    option(page, 2).click()
    next_question(page)

    page.locator("#results").wait_for()

    # Open the restart confirmation.
    page.get_by_role("button", name="Restart Quiz").click()

    confirmation = page.locator("#restart-confirm")
    assert confirmation.is_visible()

    # Confirm the restart.
    confirmation.get_by_role("button", name="Confirm restart").click()

    assert page.locator("#question").inner_text() == "What is 2 + 2?"
    assert page.locator("#question-number").input_value() == "1"

    # The question should be answerable again.
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

    # Question 1: A and C are both wrong.
    option(page, 0).click()
    option(page, 2).click()

    # The correct answer should have been revealed automatically.
    assert "correct" in (option(page, 1).get_attribute("class") or "")
    assert page.locator("#explanation").is_visible()

    # The question remains classified as wrong, not skipped.
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

    # Jump directly to Question 3.
    page.locator("#question-number").fill("3")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "3"
    assert page.locator("#question").inner_text() == "Which number is even?"

    # Values above the last question are clamped to the last question.
    page.locator("#question-number").fill("999")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "3"

    # Values below the first question are clamped to the first question.
    page.locator("#question-number").fill("0")
    page.locator("#question-number").press("Enter")

    assert page.locator("#question-number").input_value() == "1"
    assert page.locator("#question").inner_text() == "What is 2 + 2?"


def test_keyboard_controls(page_with_quiz):
    """Keyboard shortcuts answer questions and navigate the quiz."""
    page = page_with_quiz

    # Number keys select the corresponding option.
    page.keyboard.press("2")

    assert "correct" in (option(page, 1).get_attribute("class") or "")

    # Enter after revealing advances to the next question.
    page.keyboard.press("Enter")

    assert page.locator("#question-number").input_value() == "2"
    assert page.locator("#question").inner_text() == ("What is the capital of France?")

    # Right arrow moves forward.
    page.keyboard.press("ArrowRight")

    assert page.locator("#question-number").input_value() == "3"

    # Left arrow moves backward.
    page.keyboard.press("ArrowLeft")

    assert page.locator("#question-number").input_value() == "2"

    # h/l are aliases for left/right navigation.
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

    # Run the actual save logic without depending on the confirmation prompt.
    page.evaluate("saveEdit()")

    # Close the editor without testing the confirmation UI.
    page.evaluate("closeEditor()")

    assert page.locator("#question").inner_text() == "What is 10 + 10?"

    options = page.locator("#options button")
    assert options.count() == 3
    assert options.nth(0).inner_text() == "19"
    assert options.nth(1).inner_text() == "21"
    assert options.nth(2).inner_text() == "20"

    # The new correct answer should work.
    options.nth(2).click()
    assert "correct" in (options.nth(2).get_attribute("class") or "")
