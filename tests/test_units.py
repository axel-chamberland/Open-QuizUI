import os
import json
import pytest

from openquizui.quiz_function import clean_text, parse_quiz

TEST_DIR = "tests/test_files"


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

    output: tuple[str, list[dict]] = parse_quiz(clean_text(content, True, True))

    os.makedirs("tmp", exist_ok=True)
    with open(f"tmp/{file.replace('.json', '.out')}", "w") as f:
        f.write(json.dumps({"expected": output}))

    assert output[0] == expected[0], (
        f"\nDifferent title recieved. FILE: {file}\nEXPECTED: {expected[0]}\nGOT: {output[0]}. \n This may not be a bad thing: verify the title."
    )
    assert output[1] == expected[1], (
        f"\nDifferent questions recieved. FILE: {file}\nEXPECTED: {expected[1]}\nGOT: {output[1]}. \n."
    )
