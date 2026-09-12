import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse

from backend.build import TOOL_FILE, TOOL_OUTPUT, build

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def tool_class():
    """Build once and load the generated Tools class."""

    build(TOOL_FILE, TOOL_OUTPUT)

    assert TOOL_OUTPUT.exists(), f"Build did not produce {TOOL_OUTPUT}"

    spec = importlib.util.spec_from_file_location(
        "built_tool_function",
        TOOL_OUTPUT,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules["built_tool_function"] = module
    spec.loader.exec_module(module)

    return module.Tools


@pytest.fixture
def quiz_tool(tool_class):
    return tool_class()


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
    questions = [{"question": "Where is the answer?"}]

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, str)
    assert "no valid questions could be recovered" in response


@pytest.mark.asyncio
async def test_generate_quiz_theme_light(quiz_tool):
    """Test that setting dark_mode to 0 applies the light theme CSS."""
    title = "Light Mode Quiz"
    questions = [{"question": "Is it light?", "answer": "Yes", "distractors": ["No"]}]
    quiz_tool.valves.dark_mode = 0

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)

    body = response.body.decode("utf-8")

    assert "--bg: oklch(100% 0 0);" in body
    assert "--bg: oklch(20% 0 0);" not in body


@pytest.mark.asyncio
async def test_generate_quiz_theme_dark(quiz_tool):
    """Test that setting dark_mode to 1 applies the dark theme CSS."""
    title = "Dark Mode Quiz"
    questions = [{"question": "Is it dark?", "answer": "Yes", "distractors": ["No"]}]
    quiz_tool.valves.dark_mode = 1

    response = await quiz_tool.generate_quiz(title, questions)

    assert isinstance(response, HTMLResponse)

    body = response.body.decode("utf-8")

    assert "--bg: oklch(20% 0 0);" in body
    assert "--bg: oklch(100% 0 0);" not in body


@pytest.mark.asyncio
async def test_generate_mathjax(quiz_tool):
    """Test enabling MathJax."""
    title = "Math Quiz"
    questions = [
        {"question": "What is $x$?", "answer": "Variable", "distractors": ["Number"]}
    ]
    quiz_tool.valves.enable_mathjax = True

    response = await quiz_tool.generate_quiz(title, questions)
    body = response.body.decode("utf-8")

    assert isinstance(response, HTMLResponse)
    assert "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" in body
