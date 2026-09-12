import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from backend.build import ACTION_FILE, ACTION_OUTPUT, build

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests" / "test_files"


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
