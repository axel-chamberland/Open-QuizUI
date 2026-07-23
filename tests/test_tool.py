import pytest
from fastapi.responses import HTMLResponse
from openquizui.quiz_tool import Tools


@pytest.fixture
def quiz_tool():
    return Tools()


@pytest.mark.asyncio
async def test_generate_quiz_success(quiz_tool):
    """Test that a valid quiz generates an HTMLResponse with the correct title."""
    title = "Test Quiz"
    questions = [{"question": "What is 2+2?", "answer": "4", "distractors": ["3", "5"]}]

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)
    assert title in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_generate_quiz_invalid_type(quiz_tool):
    """Test that providing a non-list for questions returns an error message."""
    title = "Bad Type Quiz"
    questions = "not a list"

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, str)
    assert "must be a list of question objects" in response


@pytest.mark.asyncio
async def test_generate_quiz_missing_keys(quiz_tool):
    """Test that providing questions with missing keys returns an error message."""
    title = "Missing Keys Quiz"
    questions = [
        {"question": "Where is the answer?"}  # Missing 'answer' and 'distractors'
    ]

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, str)
    assert "no valid questions could be recovered" in response


@pytest.mark.asyncio
async def test_generate_quiz_theme_light(quiz_tool):
    """Test that setting dark_mode to 0 (Light Mode) applies the light theme CSS."""
    title = "Light Mode Quiz"
    questions = [{"question": "Is it light?", "answer": "Yes", "distractors": ["No"]}]
    quiz_tool.valves.dark_mode = 0

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)
    # Check if the default light theme CSS variables are present (e.g., --bg: oklch(100% 0 0))
    assert "--bg: oklch(100% 0 0);" in response.body.decode("utf-8")
    assert "--bg: oklch(20% 0 0);" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_generate_quiz_theme_dark(quiz_tool):
    """Test that setting dark_mode to 1 (Dark Mode) applies the dark theme CSS."""
    title = "Dark Mode Quiz"
    questions = [{"question": "Is it dark?", "answer": "Yes", "distractors": ["No"]}]
    quiz_tool.valves.dark_mode = 1

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)
    # Check if the default dark theme CSS variables are present (e.g., --bg: oklch(20% 0 0))
    assert "--bg: oklch(20% 0 0);" in response.body.decode("utf-8")
    assert "--bg: oklch(100% 0 0);" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_generate_quiz_mathjax_enabled(quiz_tool):
    """Test enabling MathJax."""
    title = "Math Quiz"
    questions = [
        {"question": "What is $x$?", "answer": "Variable", "distractors": ["Number"]}
    ]
    quiz_tool.valves.enable_mathjax = True

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)
    assert (
        "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
        in response.body.decode("utf-8")
    )
    assert "const ENABLE_MATHJAX = true;" in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_generate_quiz_mathjax_disabled(quiz_tool):
    """Test disabling MathJax."""
    title = "No Math Quiz"
    questions = [
        {"question": "What is $x$?", "answer": "Variable", "distractors": ["Number"]}
    ]
    quiz_tool.valves.enable_mathjax = False

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)
    assert "const ENABLE_MATHJAX = false;" in response.body.decode("utf-8")
