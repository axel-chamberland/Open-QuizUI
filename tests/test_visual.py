import os
import json
import pytest

from openquizui.quiz_function import Action

TEST_DIR = "tests/test_files"


def minimal_body(content: str):
    return {"messages": [{"role": "user", "content": content}]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file", [f for f in os.listdir(TEST_DIR) if f.endswith(".json")]
)
async def test_each_case(file):
    action = Action()

    action.valves = Action.Valves(
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


def extract_output(result):
    if hasattr(result, "body"):
        body = result.body
        if isinstance(body, memoryview):
            body = body.tobytes()
        return body.decode() if isinstance(body, (bytes, bytearray)) else str(body)

    return str(result)
