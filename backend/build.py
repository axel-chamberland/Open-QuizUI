import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ACTION_FILE = ROOT / "backend" / "quiz_function.py"
TOOL_FILE = ROOT / "backend" / "quiz_tool.py"
HTML_FILE = ROOT / "frontend" / "index.html"
BASE_CSS = ROOT / "frontend" / "styles" / "base.css"
ACTION_OUTPUT = ROOT / "release" / "action_function.py"
TOOL_OUTPUT = ROOT / "release" / "tool.py"


THEMES_SRC = '''# =========================
# THEME -- Feel free to add your own theme or modify presets
# =========================
"""
OpenWebUI default color scheme:
    --color-gray-50: oklch(98% 0 0);
    --color-gray-100: oklch(94% 0 0);
    --color-gray-200: oklch(92% 0 0);
    --color-gray-300: oklch(85% 0 0);
    --color-gray-400: oklch(77% 0 0);
    --color-gray-500: oklch(69% 0 0);
    --color-gray-600: oklch(51% 0 0);
    --color-gray-700: oklch(42% 0 0);
    --color-gray-800: oklch(32% 0 0);
    --color-gray-900: oklch(20% 0 0);
    --color-gray-950: oklch(16% 0 0);
"""

THEMES = {
    "default_light": """
--bg: oklch(100% 0 0);
--btn: oklch(94% 0 0);
--text: oklch(20% 0 0);
--border: oklch(85% 0 0);

--success: #0fff93;
--danger: #ff4545;
--skipped: #ffb800;
--unanswered: #8a8a8a;

--correct_bg: color-mix(in srgb, var(--success) 30%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 30%, var(--btn));
""",
    "default_dark": """
--bg: oklch(20% 0 0);
--btn: oklch(24% 0 0);
--text: oklch(94% 0 0);
--border: oklch(85% 0 0);

--success: #00ff00;
--danger: #ff0000;
--skipped: #ffcc00;
--unanswered: #999999;

--correct_bg: color-mix(in srgb, var(--success) 30%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 30%, var(--btn));
""",
    "tokyonight": """
--bg: #1a1b26;
--btn: #242b42;
--text: #c0caf5;
--border: #7aa2f7;

--success: #1abc9c;
--danger: #ff007c;
--skipped: #e0af68;
--unanswered: #565f89;

--correct_bg: color-mix(in srgb, var(--success) 30%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 30%, var(--btn));
""",
    "high_contrast": """
--bg: #000000;
--btn: #111111;
--text: #ffffff;
--border: #ffffff;

--success: #00ff00;
--danger: #ff0000;
--skipped: #ffff00;
--unanswered: #00ffff;

--correct_bg: color-mix(in srgb, var(--success) 40%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 40%, var(--btn));
""",
    "soft_pastel": """
--bg: #fdf6f0;
--btn: #f2e9e4;
--text: #4a4a4a;
--border: #d8cfc4;

--success: #6bbf59;
--danger: #e07a5f;
--skipped: #e6b566;
--unanswered: #a8998e;

--correct_bg: color-mix(in srgb, var(--success) 25%, var(--btn));
--wrong_bg: color-mix(in srgb, var(--danger) 25%, var(--btn));
""",
}
'''

# Expose THEMES as a real name so source files can import it
# (backend/quiz_function.py imports backend.build).
_themes_ns = {}
exec(THEMES_SRC, _themes_ns)
THEMES = _themes_ns["THEMES"]


def main():
    build(ACTION_FILE, ACTION_OUTPUT)
    build(TOOL_FILE, TOOL_OUTPUT)


def build(python_file, output_file):
    # Bundle JS
    with tempfile.NamedTemporaryFile(suffix=".js") as tmp:
        subprocess.run(
            [
                "npx",
                "esbuild",
                str(ROOT / "frontend" / "src" / "main.js"),
                "--bundle",
                "--format=esm",
                f"--outfile={tmp.name}",
            ],
            check=True,
        )

        js = Path(tmp.name).read_text()

    # Read HTML
    html = HTML_FILE.read_text()

    # Inline CSS
    css = BASE_CSS.read_text()

    html = html.replace(
        '<link rel="stylesheet" href="./styles/base.css">',
        f"<style>\n{css}\n</style>",
    )

    # Remove default theme CSS.
    # Themes are supplied by Python at runtime.
    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="\./styles/base\.css"\s*/?>',
        f"<style>\n{css}\n</style>",
        html,
    )

    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="\./styles/default_theme\.css"\s*/?>',
        """<style>
    :root {
        color-scheme: light dark;
        __LIGHT_THEME__
    }

    @media (prefers-color-scheme: dark) {
        :root {
            __DARK_THEME__
        }
    }
    </style>""",
        html,
    )

    # Replace demo quiz data with a placeholder
    html = re.sub(
        r'<script id="app-data" type="application/json">.*?</script>',
        '<script id="app-data" type="application/json">__APP_DATA__</script>',
        html,
        flags=re.DOTALL,
    )

    # Inline bundled JS
    html = html.replace(
        '<script type="module" src="./src/main.js"></script>',
        f'<script type="module">\n{js}\n</script>',
    )

    python = python_file.read_text()

    python = python.split("def wrap_html(", 1)[0]

    # Strip the source-only THEMES import and inject the shared theme block
    # right after the imports, two lines before the main class.
    python = python.replace("from backend.build import THEMES\n", "")
    match = re.search(r"^class\s+\w+", python, re.MULTILINE)
    if not match:
        raise ValueError(f"No top-level class found in {python_file}")
    head = python[: match.start()].rstrip("\n") + "\n\n"
    python = head + THEMES_SRC + "\n\n" + python[match.start() :]

    python += f'''def wrap_html(
    quiz,
    enable_mathjax: bool,
    light_theme="default_light",
    dark_theme="default_dark",
    default_mode="mcq",
    request_retention=20,
    spaced_repetition_queue_size=0.9,
):

    import json

    payload = {{
        "enableMathJax": bool(enable_mathjax),
        "mode": default_mode,
        "srsQueueSize": spaced_repetition_queue_size,
        "requestRetention": request_retention,
        "quiz": quiz,
    }}

    app_data = json.dumps(payload, ensure_ascii=False)

    return (
        HTML_TEMPLATE
        .replace("__APP_DATA__", app_data)
        .replace("__LIGHT_THEME__", light_theme)
        .replace("__DARK_THEME__", dark_theme)
    )


HTML_TEMPLATE = r"""{html}"""
'''

    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(python)

    print(f"Built: {output_file}")


if __name__ == "__main__":
    main()
