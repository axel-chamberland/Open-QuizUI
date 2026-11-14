import difflib
import json
import os

import pytest

from backend import quiz_function, quiz_tool
from backend.quiz_function import clean_message, parse_quiz

TEST_DIR = "tests/test_files"


@pytest.mark.parametrize("backend", [quiz_function, quiz_tool])
def test_backslash_math_delimiters(backend):
    inline = r"\(x < y\)"
    display = "\\[\nx > y\n\\]"
    text = f"{inline}\n\n{display}"
    assert clean_message(text, True, True) == text
    assert backend._markdown_to_html(text) == f"<p>{inline}</p>\n<p>{display}</p>"


@pytest.mark.parametrize("backend", [quiz_function, quiz_tool])
def test_markdown_conversion_preserves_math_verbatim(backend):
    text = "$x > y$ and $x < y$ and $x &lt; y$\n\n$$\na & b\n$$"
    assert backend._markdown_to_html(text) == (
        "<p>$x > y$ and $x < y$ and $x &lt; y$</p>\n<p>$$\na & b\n$$</p>"
    )


@pytest.mark.parametrize("backend", [quiz_function, quiz_tool])
def test_inline_math_does_not_span_blockquotes(backend):
    text = "$5\n\n> quote\n\n$3"
    assert "<blockquote>" in backend._markdown_to_html(text)


@pytest.mark.parametrize("backend", [quiz_function, quiz_tool])
@pytest.mark.parametrize("delimiter", ["$", "$$"])
def test_markdown_conversion_preserves_latex_escapes(backend, delimiter):
    text = delimiter + r"\text{a\_b} + \{x\}" + delimiter
    assert backend._markdown_to_html(text) == f"<p>{text}</p>"


def minimal_body(content: str):
    return {"messages": [{"role": "user", "content": content}]}


@pytest.mark.parametrize(
    "file", [f for f in os.listdir(TEST_DIR) if f.endswith(".json")]
)
def test_each_case(file):

    path = os.path.join(TEST_DIR, file)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "content" in data, (
        f"The test file, {file}, is missing 'content': {data.keys()}"
    )

    assert "expected" in data, (
        f"The test file, {file}, is missing 'expected' field: {data.keys()}"
    )

    content: str = data["content"]
    expected: list[str | list[dict]] = data["expected"]

    output: tuple[str, list[dict]] = parse_quiz(
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


def test_markdown_table():
    content = """## Question #1

Which planet has the largest diameter?

| Planet | Approx. diameter |
|---|---|
| Earth | 12,742 km |
| Mars | 6,779 km |
| Jupiter | 139,820 km |
| Neptune | 49,244 km |

A. Earth
B. Mars
C. Jupiter
D. Neptune

**Answer:** C. Jupiter — 139,820 km
"""

    output = parse_quiz(
        clean_message(content, True, True),
        True,
    )

    question = output[1][0]

    assert "<table>" in question["question"]
    assert "<th>Planet</th>" in question["question"]
    assert "<td>Jupiter</td>" in question["question"]
    assert "<td>139,820 km</td>" in question["question"]

    assert question["options"] == [
        "<p>Earth</p>",
        "<p>Mars</p>",
        "<p>Jupiter</p>",
        "<p>Neptune</p>",
    ]

    assert question["correct_index"] == 2


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
