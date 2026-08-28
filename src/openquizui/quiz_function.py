"""
title: QuizUI
author: Axel Chamberland
git_url: https://github.com/axel-chamberland/OpenQuizUI
description: Converts a multiple choice quiz message into an interactive HTML quiz
version: 1.0
"""

from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
import re
import json
import random
import base64

# =========================
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


# Icon for the action function
# char = "🃍"
# svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
# <text x="12" y="18" text-anchor="middle" font-size="20" fill="currentColor" stroke="currentColor" stroke-width="0.5">{char}</text>
# </svg>"""


class Action:
    #    icon_url = "data:image/svg+xml;base64," + base64.b64encode(
    #        svg.encode("utf-8")
    #    ).decode("ascii")

    class Valves(BaseModel):
        shuffle_choices: bool = Field(
            default=True,
            description="Shuffle the order of choices",
        )
        enable_mathjax: bool = Field(
            default=False,
            description="Disabled by default for privacy and performance. Enable LaTeX/math rendering with MathJax. Requires Internet access to load the MathJax library from a CDN. When disabled or offline, LaTeX expressions are displayed as plain text.",
        )

        strip_references: bool = Field(
            default=False,
            description="Remove reference-style link definitions: [id]: url",
        )

        strip_ending_brackets: bool = Field(
            default=True,
            description="LLMs will sometimes give the answer inline in [brackets], or a hint that gives off the answer. This may interfere with some questions.",
        )

        dark_mode: int = Field(
            default=-1,
            description="-1: Let browser decide. 0: Light mode. 1: Dark mode",
        )
        light_theme: str = Field(
            default="default_light",
            description="change the dark mode theme to a different theme. to define a new theme, you can add a theme at the top of the code where the templates are. Defaults: default_light, soft_pastel",
        )
        dark_theme: str = Field(
            default="default_dark",
            description="change the dark mode theme to a different theme. to define a new theme, you can add a theme at the top of the code where the templates are. Defaults: default_dark. high_contrast, tokyonight",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self, body: dict, __event_emitter__, __event_call__=None, __user__=None
    ):

        try:
            # Take latest message.
            # Contrary to the API endpoint which has output field, the body element only contains
            # the raw content with reasoning blocks included.
            # Verify with:
            # prints = []
            # for k, v in body["messages"][-1].items():
            #     prints.append((k, type(v)))
            # raise Exception(f"{prints}")

            # return HTMLResponse(
            #     content=f"<code>{json.dumps(body)}</code>",
            #     headers={"Content-Disposition": "inline"},
            # )

            # Bugged as of 10.0:
            #             text = body["messages"][1]["content"]

            text = body["messages"][-1]["content"]

            if text == "":
                # Alternative: get correct chat from backend
                from open_webui.models.chats import (
                    Chats,
                )  # full path: open-webui/backend/open_webui/models/chats

                chat_id = body["chat_id"]
                msg_id = body["messages"][-1]["id"]
                message = await Chats.get_message_by_id_and_message_id(chat_id, msg_id)

                text = message["output"][-1]["content"][-1]["text"] if message else ""

            # Remove HTML tags, reasoning blocks and other artifacts
            text = clean_text(
                text, self.valves.strip_references, self.valves.strip_ending_brackets
            )

            if not text:
                raise ValueError("No content received")

            title, questions = parse_quiz(text)

            if self.valves.shuffle_choices:
                shuffle_options(questions)

            quiz = {"title": title, "questions": questions}

            # Modify Theme

            option_dark = self.valves.dark_theme
            option_light = self.valves.light_theme

            if self.valves.dark_mode == 0:
                option_dark = option_light
            elif self.valves.dark_mode == 1:
                option_light = option_dark

            dark_theme = THEMES.get(option_dark, THEMES["default_dark"])
            light_theme = THEMES.get(option_light, THEMES["default_light"])

            # Generate quiz
            content = wrap_html(
                quiz, self.valves.enable_mathjax, light_theme, dark_theme
            )

            return HTMLResponse(
                content=content,
                headers={"Content-Disposition": "inline"},
            )

        except Exception as e:
            await __event_emitter__(
                {
                    "type": "notification",
                    "data": {"type": "error", "content": f"Action failed: {str(e)}"},
                }
            )
        return {"content": "Action encountered an error"}


# =========================
# PARSER
# =========================


def parse_quiz(
    text: str,
) -> tuple[str, list[dict]]:

    lines = [line.strip() for line in text.split("\n")]

    # -------------------------
    # Parse questions
    # -------------------------

    questions, first_question_line = question_parser_standard(lines)

    # -------------------------
    # Attempt to Infer Title
    # -------------------------

    title: str = infer_title(lines, first_question_line)

    # -------------------------
    # Parse answer key (anywhere in the text)
    # -------------------------

    # We use various degrees of detection.
    # The first one is a numbered list, if not found, try the next pattern.
    # Works both if answers are below each questions or in an answer key.
    # The current regex may be too permissive, but we verify answer counts after to make up for that fact.
    # This needs polishing, as some could be redundant.
    # \*{0,2} is used to allow bold characters.
    # Asterix could also be stripped them from lines to simplify the regex.
    answer_patterns = [
        # Numbered list: 1. B
        r"^\s*\*{0,2}\d+\s*\*{0,2}\s*[\.\):-]\s*\*{0,2}([A-Z])\*{0,2}(?=\s*(?:,|$))",
        # Numbered list: 1. B (less strict)
        r"^\s*\*{0,2}\d+\s*\*{0,2}\s*[\.\):-]\s*\*{0,2}([A-Z])\*{0,2}\b",
        # Réponse : B / Answer: B / Correct answer: B or even **Answer** or **R:** or R:
        r"^\s*\*{0,2}(?:réponse|answer|correct answer|r|a)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*([A-Z])\b",
        # In Bullet Point
        r"^\s*[*\-]?\s*\*{0,2}\s*(?:r|answer|réponse|correct answer)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*([A-Z])\b",
        # **Q1 Answer:** **c) ...** / **Q1 Answer:** **c)** trailing text
        r"^\s*\*{0,2}\s*q\s*\d+\s*(?:r|answer|réponse|correct answer)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*\*{0,2}\s*([A-Z])\b",
        # Question 1 : B
        r"^\s*question\s*\d+.*?([A-Z])\b",
        # Numbered bulk: 1.A, 2.B, 3.C, 4.B, 5.A and optional | and ) delimiters
        r"\b\d+\s*\*{0,2}\s*[\.\):-]\s*\*{0,2}\s*([A-Z])\s*\)?(?=\s*(?:\||,|$|\s+\d+\s*[\.\):-]))",
        # Adding a space as option:
        r"\b\d+\s*\*{0,2}\s*[-.):\s]\s*\*{0,2}\s*([A-Z])\s*\)?(?=\s*(?:\||,|$|\s+\d+\s*[-.):\s]))",
        # In Table
        r"^\|\s*\*{0,2}\d+\*{0,2}\s*\|\s*\*{0,2}([A-Z]).*\|\s*$",
    ]

    for pattern in answer_patterns:
        matches = [
            m.group(1).upper()
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        ]

        if len(matches) == len(questions):  # Verification step
            valid = True
            for q, letter in zip(questions, matches):
                correct_index = ord(letter) - ord("A")

                # Check that the answer exists in the question's choices
                if correct_index < 0 or correct_index >= len(q["options"]):
                    valid = False
                    break

                q["correct_index"] = correct_index

            if valid:
                break
    else:
        raise ValueError(
            f"{matches}"
            "Failed to parse answers" + str(len(matches)) + "/" + str(len(questions))
        )

    return title, questions


def question_parser_standard(lines) -> tuple[list[dict], int | None]:
    """
    Formats:
    #Question 1: ...
    #Q 1. ...
    #Q1. ...
    #Question 1 - ...
    #1. ...
    **1. ...***
    1. ...
    Supports bonus question
    Supports if description is on following lines
    """

    question_re = re.compile(
        r"(?:#{1,6}\s*)?"  # Optional Markdown Header (#)
        r"(?:\*\*)?"  # Optional bold question (**)
        r"(?:(?:question|q(?![a-zÀ-ÿ])|bonus)\s*([0-9]+)?|(\*\*[0-9]+))"  # The Label/Number
        r"\s*[:.\-]?\s*"  # Separator (: . -)
        r"(?:\*\*)?"  # Skip bold end of question, if it exists
        r"(.*?)(?:\*\*)?$",  # actual question text, excluding ** if it exists
        re.IGNORECASE,
    )
    choice_re = re.compile(
        r"^\s*[-*•]?\s*([A-Z])[\)\.\-]\s*(.+)$",
        re.IGNORECASE,
    )

    questions = []
    current_question = None

    first_question_line = None
    for line_no, line in enumerate(lines):
        if not line:
            continue

        question_match = question_re.match(line)
        if question_match:
            if first_question_line is None:
                first_question_line = line_no
            if current_question and len(current_question["options"]) >= 2:
                questions.append(current_question)

            # Change to next question
            current_question = {
                "question": question_match.group(3).strip(" :-"),
                "options": [],
                "correct_index": None,
            }

            continue

        if current_question is None:
            continue

        choice_match = choice_re.match(line)

        if choice_match:
            value = choice_match.group(2)

            value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
            value = re.sub(r"\[source:.*?\]", "", value)
            value = value.strip()

            current_question["options"].append(value)

            # fallback only
            if current_question["correct_index"] is None and "**" in line:
                current_question["correct_index"] = len(current_question["options"]) - 1

            continue

        # multiline question
        if not current_question["options"]:
            if current_question["question"]:
                current_question["question"] += " "
            current_question["question"] += line

    if current_question and len(current_question["options"]) >= 2:
        questions.append(current_question)

    _verify_questions(questions)
    return questions, first_question_line


def _verify_questions(questions):
    """
    Sanity-check parsed questions and raise ValueError listing every
    problem found, rather than silently returning bad data.
    """
    errors = []

    if not questions:
        raise ValueError(
            "question_parser_standard: no questions were parsed from the input."
        )

    for i, question in enumerate(questions, start=1):
        label = f"Question {i}"

        question_text = question.get("question", "")
        if not question_text or not question_text.strip():
            errors.append(f"{label}: empty question text.")

        options = question.get("options", [])
        if len(options) < 2:
            errors.append(f"{label}: only {len(options)} option(s) found (need >= 2).")

        empty_option_idxs = [j for j, opt in enumerate(options) if not opt.strip()]
        if empty_option_idxs:
            errors.append(
                f"{label}: empty option text at index(es) {empty_option_idxs}."
            )

    if errors:
        raise ValueError(
            "question_parser_standard: found "
            f"{len(errors)} issue(s) while verifying parsed questions:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def infer_title(lines, before_line):
    """
    Look at lines BEFORE the first detected question (before_line) and pick
    the one that most resembles a title:
      1. markdown heading (# .. / ## .. / etc.)        -> strongest signal
      2/3. quoted phrase or fully-bold line             -> medium signal
      4. fallback: any reasonably-sized plain line       -> weakest signal

    Skips bracket/tag-like lines (e.g. "<details ...>", "[meta]") and blank
    lines; they're never real titles. Among equally-scored candidates,
    prefers the one closest to the question list (titles usually sit
    right before questions start, not buried in earlier chit-chat).
    """
    candidates = lines if before_line is None else lines[:before_line]

    bad_section_patterns = [
        # explicit section markers
        r"^partie\b",
        r"^section\b",
        r"^chapter\b",
        r"^chapitre\b",
        # roman/numbered section headers like "Partie A", "Section 1"
        r"^(partie|section|chapter|chapitre)\s+[a-z0-9]+",
        # generic labeled subsections like "A - something", "1 - something"
        r"^[a-z]\s*-\s+",
        r"^\d+\s*-\s+",
        # Sub heading
    ]

    def is_tag_like(s):
        return bool(re.fullmatch(r"[<\[].*[>\]]", s))

    def is_subsection_under_title(lines, i):
        # check previous non-empty line
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1

        if j < 0:
            return False

        return re.match(r"^#{1,3}\s+", lines[j]) and re.match(r"^#{4,}\s+", lines[i])

    scored = []  # (score, title_text)
    for i, line in enumerate(candidates):
        s = line.strip()
        if not s or is_tag_like(s):
            continue
        if is_subsection_under_title(candidates, i):
            continue
        heading_match = re.match(r"^#{1,6}\s*(.+)$", s)
        if heading_match:
            heading_text = heading_match.group(1).strip(" *_")

            if heading_text and not any(
                re.search(p, heading_text.lower()) for p in bad_section_patterns
            ):
                scored.append((3, heading_text))
                continue

        quote_match = re.search(r'["“]([^"”]{6,80})["”]', s)
        if quote_match:
            quoted = quote_match.group(1).strip(" *_")
            if not any(re.search(p, quoted.lower()) for p in bad_section_patterns):
                scored.append((2, quoted))
                continue

        bold_match = re.fullmatch(r"\*\*(.+)\*\*[:.]?", s)
        if bold_match:
            bold_text = bold_match.group(1).strip(" *_")

            if (
                bold_text
                and len(bold_text) > 5
                and not any(
                    re.search(p, bold_text.lower()) for p in bad_section_patterns
                )
            ):
                scored.append((2, bold_text))
                continue

        clean = re.sub(r"[#*_`>-]", "", s).strip()
        if (
            clean
            and len(clean) > 5
            and not any(re.search(p, clean.lower()) for p in bad_section_patterns)
        ):
            scored.append((1, clean))

    if not scored:
        return "Quiz"

    best_score = max(s[0] for s in scored)
    best = [c for c in scored if c[0] == best_score]
    return best[-1][1]


# =========================================================
# HELPERS
# =========================================================


def clean_text(text: str, strip_refs: bool, strip_end_brackets: bool):
    """
    Remove HTML tags and thinking blocks.
    """
    # Delete reasoning/tool-call blocks entirely (tag + body)
    text = re.sub(
        r'<details\s+type=["\'](?:reasoning|tool_calls)["\'][^<>]*>.*?</details>',
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # For any remaining <details> (plain spoiler/answer-key blocks),
    # unwrap: drop the <summary>...</summary> label, keep the rest of the body
    text = re.sub(r"<summary>.*?</summary>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?details[^<>\n]*>", "", text, flags=re.IGNORECASE)

    # Remove reference-style link definitions: [id]: url
    if strip_refs:
        text = re.sub(r"\s*\[\d+\]\s*$", "", text, flags=re.MULTILINE)

    # LLMs will sometimes give the answer inline in brackets, or a hint that gives off the answer
    if strip_end_brackets:
        text = re.sub(r"\s*\[[^\]]*\]\s*$", "", text, flags=re.MULTILINE)
    return text.strip().replace("\r", "")


# =========================
# QUIZ LOGIC
# =========================


def shuffle_options(questions: list[dict]):

    if not questions:
        return "Quiz", [
            {
                "question": "No valid questions detected from input",
                "options": ["Check formatting", "Ensure Q/A structure"],
                "correct_index": 0,
            }
        ]

    for question in questions:
        choices = question["options"]

        indices = [x for x in range(len(question["options"]))]
        random.shuffle(indices)

        shuffled_options = []
        new_correct_index = None
        for new_idx, old_idx in enumerate(indices):
            shuffled_options.append(choices[old_idx])
            if old_idx == question["correct_index"]:
                new_correct_index = new_idx

        question["options"] = shuffled_options
        question["correct_index"] = new_correct_index


# =========================
# HTML WRAPPER
# =========================


def wrap_html(quiz, enable_mathjax: bool, light_theme, dark_theme):
    quiz_json = json.dumps(quiz)

    rendered_script = script.replace(
        "__ENABLE_MATHJAX__", "true" if enable_mathjax else "false"
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quiz</title>

<style>
{style.format(light_theme=light_theme, dark_theme=dark_theme)}
</style>
</head>

<body>
{svg_icons}
<div class="question-box">
    <div id="titleBar">
        <h1 id="title"></h1>
        <span id="timer">00:00</span>
    </div>
    <div class="navigation-scroll">

        <div id="navigation">

            <button id="prevButton" onclick="prevQuestion()">&lt;</button>

            <div id="questionSelector">
                <input id="questionNumber" type="text" inputmode="numeric" value="1">
                <span class="separator">/</span>
                <span id="questionCount">1</span>
            </div>

            <button id="nextButton" onclick="nextQuestion()">&gt;</button>

            <button id="revealButton" onclick="revealAnswer()" aria-label="Reveal answer">
                <svg><use href="#icon-reveal"></use></svg>
            </button>

            <button id="maximizeButton" onclick="toggleFullscreen()" aria-label="Fullscreen">
                <svg><use href="#icon-fullscreen"></use></svg>
            </button>

            <button id="downloadButton" onclick="downloadQuizHTML()" aria-label="Download">
                <svg><use href="#icon-download"></use></svg>
            </button>

            <button id="timerToggle" onclick="toggleTimer()" aria-label="Timer">
                <svg><use href="#icon-timer"></use></svg>
            </button>

            <button id="editorButton" onclick="openEditor()" aria-label="Editor">
                <svg><use href="#icon-editor"></use></svg>
            </button>

        </div>
    </div>
    <p id="question"></p>
    <div id="options"></div>
</div>
<div id="results" style="display: none;">


    <div class=navigation-scroll>
        <div id="results-navigation">
            <button onclick="prevQuestion()">&lt</button>

            <button onclick="toggleFullscreen()" aria-label="Fullscreen">
                <svg><use href="#icon-fullscreen"></use></svg>
            </button>

            <button id="resultsDownloadButton" onclick="downloadQuizHTML()" aria-label="Download">
                <svg><use href="#icon-download"></use></svg>
            </button>
        </div>
    </div>
    <div id="results-scroll">

        <div id="time"></div>
        <div id="averageTime"></div>

        <div class="stat-row">
            <div id="correct"></div>
            <div id="wrong"></div>
        </div>
        <div class="stat-row">
            <div id="skipped"></div>
            <div id="unanswered"></div>
        </div>

        <div class="stat-row">
            <div id="score"></div>
            <div id="accuracy"></div>
        </div>


        <div id="statsChart"></div>

        <button onclick="confirmRestart()">Restart</button>
        <div id="restart-confirm" style="display: none;">
            <span>Restart quiz?</span>
            <button onclick="restartQuiz()">Yes</button>
            <button onclick="cancelRestart()">No</button>
        </div>

    <section class="correction-sheet">
        <h2>Correction</h2>
        <div id="question-corrections"></div>
    </section>
    </div>

</div>

<div id="editor" style="display: none;">

    <div class=navigation-scroll>
        <button onclick="saveEdit()">save</button>
        <button onclick="toggleFullscreen()" aria-label="Fullscreen">
            <svg><use href="#icon-fullscreen"></use></svg>
        </button>
        <button onclick="closeEditorConfirm()">close</button>
    </div>
    <p>
        <strong>Limitation:</strong>
        Changes are stored in your browser.<br>
        Download the modified quiz as a new HTML file to keep your changes permanently.
    </p>
    <div id="editor-close" style="display: none;">
        <span>Exit (unsaved changes will be lost)?</span>
        <button onclick="closeEditor()">yes</button>
        <button onclick="cancelCloseEditor()">no</button>
    </div>
    <div>
        <h2 id="editor-question"></h2>
        <div>
            <p><strong>Answer Position :</strong></p>
            <input type="number" id="editor-answer-number" inputmode="numeric"></input>
        </div>
        <p><strong>Choices:</strong></p>
        <div id="editor-distractors"></div>
    </div>
</div>



<script>
const quiz = {quiz_json};
{rendered_script}
</script>
<script>
{reportHeight}
</script>
</body>
</html>
"""


# =========================
# Height report script
# =========================

reportHeight = """
function reportHeight() {
    // Do not run when in fullscreen
    if (document.fullscreenElement) return;


    const questionBox = document.querySelector(".question-box");
    const results = document.getElementById("results");
    const editor = document.getElementById("editor");

    const visible =
        questionBox.style.display !== "none"
            ? questionBox
            : results.style.display !== "none"
                ? results
                : editor;

    const h = visible.scrollHeight;

    parent.postMessage({ type: "iframe:height", height: h }, "*");
}

window.addEventListener('load', reportHeight);

new ResizeObserver(reportHeight).observe(document.body);
"""

# =========================
# SVG icons
# =========================

svg_icons = """
<svg style="display: none;">
    <symbol id="icon-reveal" viewBox="0 0 24 24">
        <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/>
        <circle cx="12" cy="12" r="2.5"/>
    </symbol>

    <symbol id="icon-fullscreen" viewBox="0 0 24 24">
        <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/>
    </symbol>

    <symbol id="icon-download" viewBox="0 0 24 24">
        <path d="M12 3v12m0 0 5-5m-5 5-5-5M4 21h16"/>
    </symbol>

    <symbol id="icon-timer" viewBox="0 0 24 24">
        <circle cx="12" cy="13" r="8"/>
        <path d="M12 9v4l3 2M9 3h6"/>
    </symbol>

    <symbol id="icon-editor" viewBox="0 0 24 24">
        <path d="M12 3l1.5 2.5 3 .5-.5 3 2 2-2 2 .5 3-3 .5L12 19l-1.5-2.5-3-.5.5-3-2-2 2-2-.5-3 3-.5L12 3z"/>
        <circle cx="12" cy="11" r="2.5"/>
    </symbol>
</svg>
"""

#
# =========================
# STYLE
# =========================

style = """
:root {{
    color-scheme: light dark;
{light_theme}
}}

@media (prefers-color-scheme: dark) {{
    :root {{
{dark_theme}
    }}
}}
* {{
    box-sizing: border-box;
    font-family: inherit;
}}
body {{
    background: var(--bg);
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    align-items: center;
    margin: 0;
    overflow: hidden;
}}

#titleBar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}}

#title {{
    margin: 0;
}}
.question-box {{
    display: flex;
    flex-direction: column;
    color: var(--text);
    width: min(800px, 100%);
    padding: 8px
    height: auto;
}}

#question {{
    margin-bottom: 2em;
    font-size: 1.1rem;
}}

#options {{
    display: grid;
    grid-template-columns: 1;
    max-width: 100%;
    gap: 0.75rem;
    overflow-y: auto;
}}

button {{
    border: 1px solid;
    border-radius: 0.25rem;
    border-color: var(--border);
    background: var(--btn);
    cursor: pointer;
    text-align: center;
    color: var(--text);
    font-size: 1.1em;
}}

button svg {{
    width: 1em;
    height: 1em;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}}

.option{{
    padding: 1rem 3rem 1rem 3rem;
    position: relative;
    text-align: center;
}}
button:disabled {{
    opacity: 0.4;
}}
.option:hover {{
    filter: contrast(1.1);
}}

.option.correct {{
    background: var(--correct_bg);
    border-color: var(--success);
    opacity: 1;
}}

.option.wrong {{
    background: var(--wrong_bg);
    border-color: var(--danger);
    opacity: 1;
}}


.option::after{{
    position: absolute;
    right: 1rem;
    top: 50%;
    transform: translateY(-50%);
    width: 1rem;
    text-align: center;
}}

.option.correct::after {{
    content: " ✓";
    font-weight: bold;
}}

.option.wrong::after {{
    content: " ✗";
    font-weight: bold;
}}
.navigation-scroll {{
    overflow-x: auto;
    overflow-y: hidden;
}}

#navigation, #results-navigation {{

    display: flex;
    flex-wrap: nowrap;
    padding: 0.75rem;
    justify-content: center;
    gap: 0.5rem;

    width: max-content;
    min-width: 100%;
    z-index: 1000;
    border-bottom: 1px solid var(--border);
    margin-bottom: 20px;

    user-select: none;
    -webkit-user-select: none;
}}


#navigation button, #results-navigation button {{
    font-size : 2rem;


}}

#revealButton,
#maximizeButton,
#downloadButton,
#questionSelector {{
    flex: 0 0 auto;
    min-width: 2rem;
}}


#prevButton,
#nextButton {{
    flex: 1;
    font-size: clamp(1.5rem, 5vw, 2rem);
    max-width: 4rem;
}}


:fullscreen .navigation-scroll {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;

    margin-bottom: 0px;

    background: var(--bg);
    padding: 0.75rem;
    border-top: 1px solid var(--border);
    border-bottom: 0;

    overflow-x: auto;
}}

:fullscreen #navigation,
:fullscreen #results-navigation {{
    margin: 0;
    border: 0;
}}

:fullscreen .question-box {{
    padding-bottom: var(--nav-height);
}}

#questionSelector {{
    display: flex;
    align-items: center;
    white-space: nowrap;

    background: var(--btn);
    color: var(--text);

    border: 1px solid var(--border);
    border-radius: 0.25rem;

    font-size : 1.1rem;

    gap: 0.2rem;


}}


#questionNumber {{

    width: 3ch;
    text-align: center;
    font-size: 1.1rem;

    padding: 0;
    margin: 0;
    line-height: 1;

    background: transparent;
    color: var(--text);
    border: none;
    outline: none;

}}


#questionNumber:focus {{
    outline: none;
    border: none;
}}

#questionCount {{
    margin-right: 0.3em;
}}

mjx-container {{
    max-width: 100%;
    overflow-x: auto;
    white-space: normal;
}}

/* Hide timer by default */
#timer {{
    display: none;
    min-width: 4rem;
    font-size: 1.1rem;
    text-align: center;
    font-variant-numeric: tabular-nums;
}}
#timer.visible {{
    display: inline-block;
}}

#correct {{
    color: var(--success);
}}

#wrong {{
    color: var(--danger);
}}

#unanswered {{
    color: var(--unanswered);
}}

#skipped {{
    color: var(--skipped);
}}

.chart-correct   {{ stroke: var(--success); }}
.chart-wrong     {{ stroke: var(--danger); }}
.chart-unanswered{{ stroke: var(--unanswered); }}
.chart-skipped   {{ stroke: var(--skipped); }}

#results {{
    display: flex;
    flex-direction: column;
    width: 100%;
    height: auto;
}}

:fullscreen #results {{
    min-height: 100vh;
}}

#results-scroll {{
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
    max-height: 600px;
    max-width: 700px;
    margin: 0 auto;
    text-align: center;
    overflow-y: auto;
}}

:fullscreen #results-scroll {{
    flex: 1;
    max-height: none;
}}

.stat-row {{
    display: flex;
    gap: 1rem;
}}

.stat-row > div {{
    flex: 1;
    padding: 0.5rem;
    border-radius: 0.5rem;
    background: var(--btn);
}}

#statsChart {{
    height: min(50vh, 500px);
    align-self: center;
}}

.correction-sheet {{
    border-top: 1px solid var(--border);
    text-align: left;
}}

.correction-sheet article {{
    padding: 1rem 0;
    border-bottom: 1px solid var(--border);
}}

.correction-sheet h2 {{
    margin-bottom: 1rem;
}}

.correction-sheet h3 {{
    margin-top: 0;
}}

.correction-sheet p {{
    margin: 0.5rem 0;
}}

#editor-distractors article {{
    display: flex;
    align-items: center;
    margin-bottom: 16px;
}}

#editor-distractors textarea {{
    width: 80%;
    height: 50px;
}}

#editor-distractors .delete-prompt {{
    display: none;
}}
"""


# =========================
# SCRIPT (Front End)
# =========================

script = r"""
// Try to load math library (WARNING: requires internet)
const ENABLE_MATHJAX = __ENABLE_MATHJAX__;

let mathReady = false;

let wrongAnswerCount = 0;


let optionButtons = [];
let currentQuestion = null;

let answerRevealed = false;

// Timer
let timerVisible = false;
let timerStart = null;
let timerElapsed = 0;
let timerInterval = null;

// Key for local storage
const quizStorageKey = hashQuiz(quiz);

// Stats
const UNANSWERED = 0;
const CORRECT = 1;
const WRONG = 2;
const SKIPPED = 3;
let questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
let questionAnswers = new Array(quiz.questions.length).fill(null);
let defaultStartDate = Date.now() // Default start date used if timer was never started
loadStats();

// Question editing
loadQuizEdits();

const timer = document.getElementById("timer");
const questionBox = document.querySelector(".question-box");
const questionText = questionBox.querySelector("#question");
const optionsContainer = document.getElementById("options");
const navigationContainer = questionBox.querySelector("#navigation");
const questionNumber = document.getElementById("questionNumber");
const results = document.getElementById("results");


// Update title
document.getElementById("title").textContent = quiz.title;

// Update max question count
const questionCount = document.getElementById("questionCount");

questionCount.textContent = quiz.questions.length;

let currentQuestionIndex = getStoredQuestionIndex();
questionNumber.value = currentQuestionIndex + 1;



window.MathJax = {
    tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']]
    }
};

function loadMathJax() {
    return new Promise((resolve) => {
        if (!ENABLE_MATHJAX) {
            mathReady = false;
            resolve(false);
            return;
        }

        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";

        script.onload = () => {
            mathReady = true;
            resolve(true);
        };

        script.onerror = () => {
            mathReady = false;
            resolve(false);
        };

        document.head.appendChild(script);
    });
}

// UI events

// Get height of navigation bar for CSS (fullscreen mode)
const nav = document.getElementById("navigation");

function updateNavHeight() {
    document.documentElement.style.setProperty(
        "--nav-height",
        `${nav.offsetHeight}px`
    );
}

updateNavHeight();
new ResizeObserver(updateNavHeight).observe(nav);
window.addEventListener("resize", updateNavHeight);


function toggleFullscreen() {
    const el = document.documentElement;

    if (!document.fullscreenElement) {
        el.requestFullscreen?.();
    } else {
        document.exitFullscreen?.();
    }
}

// Helpers

function renderMath(text) {
    if (!text) return "";

    return text.replace(/\$(.+?)\$/g, (match, expr) => {
        if (mathReady && window.MathJax) {
            return match;
        }
        return `<code>${expr}</code>`;
    });
}

function renderInlineMarkdown(text) {
    if (!text) return "";

    text = text
        .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
        .replace(/\*(.*?)\*/g, "<i>$1</i>")

    return renderMath(text);
}

function renderMarkdown(text) {
    if (!text) return "";
    return renderInlineMarkdown(text).replace(/\n/g, "<br>");
}


async function renderQuiz() {
    const questionBox = document.querySelector(".question-box");
    const questionText = questionBox.querySelector("#question");
    const optionsContainer = document.getElementById("options");
    const navigationContainer = questionBox.querySelector("#navigation");

    if (!quiz.questions || quiz.questions.length === 0) {
        document.getElementById("question").textContent = "No valid questions parsed";
        return;
    }

    // Update question
    questionText.innerHTML = renderMarkdown(quiz.questions[currentQuestionIndex].question);

    // Clear and rebuild options
    optionsContainer.innerHTML = '';
    wrongAnswerCount = 0; // Answer button is revealed when user exhausted all options
    optionButtons = [];

    currentQuestion = quiz.questions[currentQuestionIndex];
    currentQuestion.options.forEach((option, index) => {
        const button = document.createElement("button");
        button.innerHTML = renderMarkdown(option);
        button.className = "option";

        optionButtons.push(button);

        button.addEventListener("click", () => {
            handleAnswer(index, button);
        });

        optionsContainer.appendChild(button);
    });
    // Update button states
    const prevButton = navigationContainer.querySelector("#prevButton");
    prevButton.disabled = currentQuestionIndex === 0;

    // Next button is not disabled as it goes to the result screen after last question
    // const nextButton = navigationContainer.querySelector("#nextButton");
    // nextButton.disabled = currentQuestionIndex === quiz.questions.length - 1;


    try {
        await MathJax.typesetPromise();
    } catch (err) {
        console.error(err);
    }



}

function nextQuestion() {
    if (currentQuestionIndex >= quiz.questions.length - 1 &&
        results.style.display === "none") {
        renderResults();
        return
    };
    goTo(currentQuestionIndex + 1)
}

function prevQuestion() {
    const results = document.getElementById("results");

    if (results.style.display !== "none") {
        results.style.display = "none";
        document.querySelector(".question-box").style.display = "";
        renderQuiz();
        return;
    }

    if (currentQuestionIndex <= 0) return;
    goTo(currentQuestionIndex - 1);
}

document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    const key = e.key.toLowerCase();


    // Number = choose
    let index = -1;

    if (/^[1-9]$/.test(key)) {
        index = Number(key) - 1;
    }


    if (index >= 0 && index < optionButtons.length) {
        const button = optionButtons[index];
        if (!button.disabled) {
            handleAnswer(index, button);
        };
        return

    }

    // Reveal answer or go to next question
    if (key === "enter" || key == " ") {
        console.log("handled", key);
        e.preventDefault();

        if (!answerRevealed) {
            revealAnswer();
        } else {
            nextQuestion();
        }
        return;
    }

    // Navigation
    if (key === "arrowright" || key === "l") {
        e.preventDefault();
        nextQuestion();
        return;
    }

    if (key === "arrowleft" || key === "h") {
        e.preventDefault();
        prevQuestion();
        return;
    };
});

// Tap or click to change question (touch control)

questionBox.addEventListener("click", (e) => {
    if (e.target.closest("button, input")) return;

    const rect = questionBox.getBoundingClientRect();
    const x = e.clientX - rect.left;

    if (x > rect.width * 0.7) {
        if (!answerRevealed) {
            revealAnswer();
        } else {
            nextQuestion();
        }
    } else if (x < rect.width * 0.3) {
        prevQuestion();
    }
});


// Change question directly
const questionSelector = document.getElementById("questionSelector");

questionSelector.addEventListener("click", () => {
    questionNumber.focus();
    questionNumber.select();
});

questionNumber.addEventListener("change", () => {
    if (!questionNumber.value) return;

    goTo(Number(questionNumber.value) - 1);
});

function goTo(question_index) {

    // Clamp between first and last question
    question_index = Math.max(
        0,
        Math.min(question_index, quiz.questions.length - 1)
    );

    currentQuestionIndex = question_index

    setStoredQuestionIndex(currentQuestionIndex);

    answerRevealed = false;

    questionNumber.value = currentQuestionIndex + 1;
    renderQuiz();
}

function handleAnswer(index, button) {
    questionAnswers[currentQuestionIndex] = index
    saveStats();
    if (index === currentQuestion.correct_index) {

        button.classList.add("correct");
        button.disabled = true;


        if (wrongAnswerCount === 0) {
            questionResults[currentQuestionIndex] = CORRECT;
            saveStats();
        }

        optionButtons.forEach(btn => btn.disabled = true);
    } else {
        button.classList.add("wrong");
        button.disabled = true;

        questionResults[currentQuestionIndex] = WRONG;
        saveStats();

        wrongAnswerCount++;

        if (wrongAnswerCount === currentQuestion.options.length - 1) {
            revealAnswer();
        }
    }
}

function revealAnswer() {
    answerRevealed = true;

    if (questionResults[currentQuestionIndex] === UNANSWERED) {
        questionResults[currentQuestionIndex] = SKIPPED;
        saveStats();
    }
    const currentQuestion = quiz.questions[currentQuestionIndex];
    const optionsContainer = document.getElementById("options");

    // Get all buttons in the current question
    const buttons = optionsContainer.querySelectorAll("button");

    // Highlight the correct answer
    buttons[currentQuestion.correct_index].classList.add("correct");
};

// Download as HTML.
function downloadQuizHTML(filename = quiz.title) {

    // Get full document HTML
    let html = "<!DOCTYPE html>\n" + document.documentElement.outerHTML;

    // Replace the quiz content with the local edits
    const quizJSON = JSON.stringify(quiz)
        .replace(/</g, "\\u003c");

    html = html.replace(
        /const quiz = .*?;/s,
        `const quiz = ${quizJSON};`
    );

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Timer



function getTimerKey() {
    return `quizTimer_${quizStorageKey}`;
}

function loadTimer() {
    try {
        const data = JSON.parse(
            localStorage.getItem(getTimerKey())
        );

        timerElapsed = data?.elapsed || 0;
        timerStart = data?.start || null;
    } catch {
        timerElapsed = 0;
        timerStart = null;
    }
}

function saveTimer() {
    try {
        localStorage.setItem(
            getTimerKey(),
            JSON.stringify({
                elapsed: timerElapsed,
                start: timerStart
            })
        );
    } catch { }
}

function updateTimer() {
    if (!timerStart) return;

    const elapsed =
        timerElapsed + Math.floor((Date.now() - timerStart) / 1000);

    timer.textContent = formatTime(elapsed);
}

function toggleTimer() {
    timerVisible = !timerVisible;
    timer.classList.toggle("visible", timerVisible);

    if (timerVisible) {
        loadTimer();

        // Start
        if (!timerStart) {
            timerStart = Date.now();
            saveTimer();
        }

        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);

    } else {
        // Pause
        if (timerStart) {
            timerElapsed +=
                Math.floor((Date.now() - timerStart) / 1000);

            timerStart = null;
            saveTimer();
        }

        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// Render results page

function renderResults() {
    const questionBox = document.querySelector(".question-box");
    const results = document.getElementById("results");

    questionBox.style.display = "none";
    results.style.display = "";

    const correct = questionResults.filter(x => x === CORRECT).length;
    const wrong = questionResults.filter(x => x === WRONG).length;
    const unanswered = questionResults.filter(x => x === UNANSWERED).length;
    const skipped = questionResults.filter(x => x === SKIPPED).length;

    const total = quiz.questions.length;
    const answered = correct + wrong;

    const accuracy = answered > 0
        ? (correct / answered) * 100
        : 0;

    const elapsed = timerVisible
        ? timerElapsed + Math.floor((Date.now() - timerStart) / 1000)
        : Math.floor((Date.now() - defaultStartDate) / 1000);


    const chartData = {
        labels: [
            "Correct",
            "Wrong",
            "Unanswered",
            "Skipped"
        ],
        datasets: [{
            label: "Score Chart",
            data: [correct, wrong, unanswered, skipped],
            classNames: ["chart-correct", "chart-wrong", "chart-unanswered", "chart-skipped"]
        }]
    };
    document.getElementById("score").textContent =
        `Score: ${correct}/${wrong + correct}`;

    document.getElementById("accuracy").textContent =
        `Accuracy: ${accuracy.toFixed(1)}%`;

    document.getElementById("correct").textContent =
        `Correct: ${correct}`;

    document.getElementById("wrong").textContent =
        `Wrong: ${wrong}`;

    document.getElementById("unanswered").textContent =
        `Unanswered: ${unanswered}`;

    document.getElementById("skipped").textContent =
        `Skipped: ${skipped}`;

    document.getElementById("time").textContent =
        `Time: ${formatTime(elapsed)}`;

    document.getElementById("averageTime").textContent =
        `Average time per question: ${formatTime(
            Math.floor(elapsed / total)
        )}`;

    createDonutChart(document.getElementById("statsChart"), chartData);
    showCorrectionSheet();
}

function createDonutChart(container, data) {
    const viewSize = 100;
    const center = viewSize / 2;

    const outerRadius = 37.5;
    const innerRadius = 20;
    const midRadius = (outerRadius + innerRadius) / 2;
    const strokeWidth = outerRadius - innerRadius;

    const circumference = 2 * Math.PI * midRadius;

    const values = data.datasets[0].data;
    const classNames = data.datasets[0].classNames;
    const total = values.reduce((sum, v) => sum + v, 0);

    let offset = 0;

    const arcs = values.map((value, i) => {
        if (value === 0 || total === 0) return "";

        const fraction = value / total;
        const dash = fraction * circumference;
        const gap = circumference - dash;

        const circle = `<circle
class="${classNames[i]}"
cx="${center}" cy="${center}" r="${midRadius}"
fill="none"
stroke-width="${strokeWidth}"
stroke-dasharray="${dash} ${gap}"
stroke-dashoffset="${-offset}"
transform="rotate(-90 ${center} ${center})"
/>`;

        offset += dash;
        return circle;
    }).join("");

    container.innerHTML = `
<svg viewBox="0 0 ${viewSize} ${viewSize}" preserveAspectRatio="xMidYMid meet" style="width: 100%; height: 100%; display: block;">
    ${arcs}
</svg>
`;
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getStatsKey() {
    return `quizStats_${quizStorageKey}`;
}

function loadStats() {
    try {
        const data = JSON.parse(localStorage.getItem(getStatsKey()));

        if (Array.isArray(data?.results)) {
            questionResults = data.results;
        }

        if (Array.isArray(data?.answers)) {
            questionAnswers = data.answers;
        }

        if (data?.startDate) {
            defaultStartDate = data.startDate;
        }
    } catch {
        questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
        questionAnswers = new Array(quiz.questions.length).fill(null);
        defaultStartDate = Date.now();
    }
}

function saveStats() {
    try {
        localStorage.setItem(
            getStatsKey(),
            JSON.stringify({
                results: questionResults,
                answers: questionAnswers,
                startDate: defaultStartDate
            })
        );
    } catch { }
}

function restartQuiz() {

    // Reset question state
    currentQuestionIndex = 0;
    questionNumber.value = 1;
    answerRevealed = false;
    wrongAnswerCount = 0;

    // Reset stats
    questionResults = new Array(quiz.questions.length).fill(UNANSWERED);
    questionAnswers = new Array(quiz.questions.length).fill(null);
    document.getElementById("question-corrections").innerHTML = "";

    // Reset timer
    clearInterval(timerInterval);
    timerInterval = null;

    timerElapsed = 0;
    timerStart = timerVisible ? Date.now() : null;
    defaultStartDate = Date.now();


    if (timerVisible) {
        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);
    } else {
        timer.textContent = formatTime(0);
    }
    saveTimer();

    // Reset stored question
    setStoredQuestionIndex(0);

    // Return to quiz
    results.style.display = "none";
    questionBox.style.display = "";

    document.getElementById("restart-confirm").style.display = "none";

    renderQuiz();
}

function confirmRestart() {
    document.getElementById("restart-confirm").style.display = "flex";
}

function cancelRestart() {
    document.getElementById("restart-confirm").style.display = "none";
}

function showCorrectionSheet() {
    const container = document.getElementById("question-corrections");
    const questions = quiz.questions;

    container.innerHTML = "";

    for (let index = 0; index < questions.length; index++) {
        const question = questions[index];

        const correctAnswer =
            question.options[question.correct_index];

        const userIndex = questionAnswers[index];

        const userAnswer =
            questionResults[index] === SKIPPED
                ? "Skipped"
                : userIndex !== null
                    ? question.options[userIndex]
                    : "Unanswered";

        const article = document.createElement("article");

        article.innerHTML = `
<h3>Question ${index + 1}</h3>

<p>${renderMarkdown(question.question)}</p>

<p>
    <strong>Your answer:</strong>
    ${renderMarkdown(userAnswer)}
</p>

<p>
    <strong>Correct answer:</strong>
    ${renderMarkdown(correctAnswer)}
</p>
`;

        container.appendChild(article);
    }
}

// Editor UI Functions

function openEditor() {
    const questionBox = document.querySelector(".question-box");
    const editor = document.getElementById("editor");

    questionBox.style.display = "none";
    editor.style.display = "";

    const questionField = document.getElementById("editor-question");
    const editorAnswer = document.getElementById("editor-answer-number");
    const optionsContainer = document.getElementById("editor-distractors");

    const question = quiz.questions[currentQuestionIndex];

    // Set initial values
    questionField.innerHTML = `<textarea>${question.question}</textarea>`;
    editorAnswer.value = question.correct_index + 1;

    question.options.forEach(option => {
        optionsContainer.appendChild(addEditorOption(option));
    });

}

function addEditorOption(value) {
    const article = document.createElement("article");

    const textarea = document.createElement("textarea");
    textarea.value = value;

    const insertBtn = document.createElement("button");
    insertBtn.textContent = "+";
    insertBtn.onclick = () => {
        article.after(addEditorOption(""));

    };

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "⌦";

    const promptDiv = document.createElement("div");
    promptDiv.className = "delete-prompt";

    const confirmBtn = document.createElement("button");
    confirmBtn.textContent = "Confirm";
    confirmBtn.onclick = () => article.remove();

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancel";
    cancelBtn.onclick = () => {
        promptDiv.style.display = "none";
    };

    deleteBtn.onclick = () => {
        promptDiv.style.display = "flex";
    };

    promptDiv.appendChild(confirmBtn);
    promptDiv.appendChild(cancelBtn);

    article.appendChild(insertBtn);
    article.appendChild(deleteBtn);
    article.appendChild(promptDiv);
    article.appendChild(textarea);

    return article;
}

function showOptionDeletePrompt(index) {
    const prompt = document.getElementById(`delete-prompt-${index}`);
    if (prompt) prompt.style.display = "flex";
}

function hideOptionDeletePrompt(index) {
    const prompt = document.getElementById(`delete-prompt-${index}`);
    if (prompt) prompt.style.display = "none";
}

// Core function to handle the deletion and answer index logic
function deleteOptionConfirmed(index) {
    const answerInput = document.querySelector('#editor-answer-number');
    const currentCorrectIndex = parseInt(answerInput.value);

    if (index === currentCorrectIndex) {
        answerInput.value = "";
        answerInput.focus();
        alert("Warning: You deleted the correct option. Please update the answer index.");
    }

    const articleToRemove = document.getElementById(`option_${index}`).parentElement;
    if (articleToRemove) {
        articleToRemove.remove();
    }
}

// Returns false if the selected answer index does not exist in the DOM anymore
function validateAnswerIndex() {
    const answerInput = document.querySelector('#editor-answer-number');

    const val = parseInt(answerInput.value) - 1;

    const optionsContainer = document.getElementById("editor-distractors");
    const options = optionsContainer.querySelectorAll("article");

    if (val < 0 || val >= options.length) {
        answerInput.classList.add('input-error');
        alert("Invalid Index: The selected option no longer exists.");
        return false;
    }

    return true;
}

function closeEditorConfirm() {
    // Validate before showing the "Are you sure?" modal
    if (!validateAnswerIndex()) {
        return; // Prevent exit
    }

    document.getElementById("editor-close").style.display = "flex";
}

function cancelCloseEditor() {
    document.getElementById("editor-close").style.display = "none";
}

function saveEdit() {

    if (!validateAnswerIndex()) {
        return;
    };

    // Extract data from DOM
    const newQuestionText = document.querySelector("#editor-question textarea").value;
    const newIndex = parseInt(document.querySelector('#editor-answer-number').value) - 1;
    const optionsContainer = document.getElementById("editor-distractors");
    const updatedOptions = Array.from(optionsContainer.querySelectorAll('textarea')).map(ta => ta.value);

    // Update global state
    quiz.questions[currentQuestionIndex].question = newQuestionText;
    quiz.questions[currentQuestionIndex].correct_index = newIndex;
    quiz.questions[currentQuestionIndex].options = updatedOptions;

    // Persist the actual changes (locally)
    saveLocalEdit(currentQuestionIndex);
}

function closeEditor() {
    const questionBox = document.querySelector(".question-box");
    const editor = document.getElementById("editor");

    editor.style.display = "none";
    document.getElementById("editor-close").style.display = "none";

    // Reset UI state
    const options = document.getElementById("editor-distractors");
    options.innerHTML = "";

    questionBox.style.display = "";

    renderQuiz();
}

function closeEditorConfirm() {
    document.getElementById("editor-close").style.display = "flex";
}

function cancelCloseEditor() {
    document.getElementById("editor-close").style.display = "none";

}


function getQuizEditsKey() {
    return `quizEdits_${quizStorageKey}`;
}

function saveLocalEdit(index) {
    const key = getQuizEditsKey();

    let edits = {};

    try {
        edits = JSON.parse(localStorage.getItem(key)) || {};
    } catch {
        edits = {};
    }

    edits[index] = quiz.questions[index];

    try {
        localStorage.setItem(key, JSON.stringify(edits));
        console.log("Saved edit:", key, edits);
    } catch (e) {
        console.error("Failed to save edit:", e);
    }
}

function loadQuizEdits() {
    const key = getQuizEditsKey();

    try {
        const edits = JSON.parse(localStorage.getItem(key));

        if (!edits) {
            return;
        }

        for (const [index, question] of Object.entries(edits)) {
            const i = Number(index);

            if (i >= 0 && i < quiz.questions.length) {
                quiz.questions[i] = question;
            }
        }
    } catch (e) {
        console.error("Failed to load quiz edits:", e);
    }
}

function hashQuiz(quiz) {

    // Hash derived from the quiz's content to avoid overlap
    const data = JSON.stringify(quiz);

    let hash = 0;
    for (let i = 0; i < data.length; i++) {
        hash = ((hash << 5) - hash) + data.charCodeAt(i);
        hash |= 0;
    }

    return `currentQuestionIndex_${hash >>> 0}`;
}

function getStoredQuestionIndex() {
    try {
        const index = Number(
            localStorage.getItem(`currentQuestionIndex_${quizStorageKey}`)
        );

        if (!Number.isInteger(index)) {
            return 0;
        }

        return Math.max(
            0,
            Math.min(index, quiz.questions.length - 1)
        );

    } catch {
        return 0;
    }
}

function setStoredQuestionIndex(value) {
    try {
        localStorage.setItem(
            `currentQuestionIndex_${quizStorageKey}`,
            String(value)
        );
    } catch (e) {
        // Ignore if storage is unavailable
    }
}


loadMathJax().then(() => {
    if (window.MathJax?.startup?.promise) {
        MathJax.startup.promise.then(renderQuiz);
    } else {
        renderQuiz();
    }
});
"""
