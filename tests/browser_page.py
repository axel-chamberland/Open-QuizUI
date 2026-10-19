"""Renders the HTML the browser smoke test loads.

Spawns from tests/browser.test.js with the app data payload as JSON on
stdin. Builds the release files from the current source, loads the
generated action function - the code Open WebUI runs - and prints the
document wrap_html() returns, so the test page is exactly what Open
WebUI serves.

Not prefixed with test_* on purpose: pytest must not collect it.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.build import ACTION_FILE, ACTION_OUTPUT, build

build(ACTION_FILE, ACTION_OUTPUT)

spec = importlib.util.spec_from_file_location(
    "browser_smoke_action", ACTION_OUTPUT
)
assert spec is not None, "Could not load the built action function"
assert spec.loader is not None

module = importlib.util.module_from_spec(spec)
sys.modules["browser_smoke_action"] = module
spec.loader.exec_module(module)

payload = json.load(sys.stdin)

sys.stdout.write(
    module.wrap_html(
        payload["quiz"],
        payload["enableMathJax"],
        default_mode=payload["mode"],
        request_retention=payload["requestRetention"],
        spaced_repetition_queue_size=payload["srsQueueSize"],
        enable_spaced_repetition=payload["srsOnLoad"],
    )
)
