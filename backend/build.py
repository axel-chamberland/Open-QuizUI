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
    html = html.replace(
        '<link rel="stylesheet" href="./styles/default_theme.css">',
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

    if "import json" not in python:
        python = "import json\n\n" + python

    python += f'''def wrap_html(
    quiz, enable_mathjax: bool, light_theme="default_light", dark_theme="default_dark"
):
    payload = {{"enableMathJax": bool(enable_mathjax), "quiz": quiz}}

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
