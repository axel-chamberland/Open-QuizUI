"""
title: QuizUI
author: Axel Chamberland
git_url: https://github.com/axel-chamberland/OpenQuizUI
description: Converts a multiple choice quiz message into an interactive HTML quiz
version: 2.0.1
"""

import random
import re

from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

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


class Action:
    icon_url = "https://raw.githubusercontent.com/axel-chamberland/Open-QuizUI/main/src/assets/action_logo.svg"

    class Valves(BaseModel):
        shuffle_choices: bool = Field(
            default=True,
            description="Shuffle the order of choices",
        )
        enable_mathjax: bool = Field(
            default=False,
            description="Disabled by default for privacy. Enable LaTeX/math rendering with MathJax. Requires Internet access to load the MathJax library from a CDN. When disabled or offline, LaTeX expressions are displayed as plain text.",
        )

        enable_explanations: bool = Field(
            default=True,
            description="Attempt to include an explanation for each question if one exists",
        )

        strip_references: bool = Field(
            default=True,
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

            text = body["messages"][-1]["content"]

            if text == "":
                # Alternative patch for 10.0 version: get correct chat from backend
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

            title, questions = parse_quiz(text, self.valves.enable_explanations)

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


# Use various degrees of detection for the answer keys (harder to detect than question keys).
# The first one is a numbered list, if not found, try the next pattern.
# Works both if answers are below each questions or in an answer key.
# The current regex may be too permissive, but we verify answer counts after to make up for that fact.
# This needs polishing, as some could be redundant.
# \*{0,2} is used to allow bold characters.
# Asterix could also be stripped them from lines to simplify the regex.
ANSWER_PATTERNS = [
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
    r"^\|\s*\*{0,2}\d+\*{0,2}\s*\|\s*\*{0,2}([A-Z])\*{0,2}(?=\s*\|)",
    # Numbered list with trailing text: 1. **B** (Vertices and edges) [1]
    # Excludes numbered questions containing '?'
    r"^\s*\*{0,2}\d+\s*\*{0,2}\s*[\.\):-]\s*\*{0,2}([A-Z])\*{0,2}(?=\s+[^?\n]+$)",
]


def parse_quiz(
    text: str,
    explanations: bool,
) -> tuple[str, list[dict]]:

    lines = [line.strip() for line in text.split("\n")]

    # -------------------------
    # Parse questions
    # -------------------------

    questions, question_lines = question_parser(lines)

    # -------------------------
    # Attempt to Infer Title
    # -------------------------

    title: str = infer_title(lines, question_lines[0])

    # -------------------------
    # Parse answer key (anywhere in the text)
    # -------------------------

    questions = answer_parser(text, questions, question_lines, explanations)

    return title, questions


def question_parser(lines) -> tuple[list[dict], list[int]]:
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
        # The Label/Number
        r"(?:(?:question|q(?![a-zÀ-ÿ])|bonus)\s*([0-9]+)?|([0-9]+)(?=\*{0,2}(?:[\s.:\)\-]|$)))"
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
    question_lines = []

    current_question = None
    current_question_line = None

    for line_no, line in enumerate(lines):
        if not line:
            continue

        question_match = question_re.match(line)
        if question_match:
            # Finish the previous question.
            if current_question and len(current_question["options"]) >= 2:
                questions.append(current_question)
                question_lines.append(current_question_line)

            # Start the new question.
            current_question = {
                "question": question_match.group(3).strip(" :-"),
                "options": [],
                "correct_index": None,
            }

            current_question_line = line_no
            continue

        if current_question is None:
            continue

        choice_match = choice_re.match(line)

        if choice_match:
            value = choice_match.group(2)

            value = re.sub(r"(?<![\w`])\*\*(.*?)\*\*(?![\w`])", r"\1", value)
            value = re.sub(r"\[source:.*?\]", "", value)
            value = value.strip()

            current_question["options"].append(value)

            # Fallback only.
            if current_question["correct_index"] is None and "**" in line:
                current_question["correct_index"] = len(current_question["options"]) - 1

            continue

        # Multiline question.
        if not current_question["options"]:
            if current_question["question"]:
                current_question["question"] += "\n"
            current_question["question"] += line

    # Finish the final question.
    if current_question and len(current_question["options"]) >= 2:
        questions.append(current_question)
        question_lines.append(current_question_line)

    _verify_questions(questions)

    return questions, question_lines


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
        r"^(part|partie|section|chapter|chapitre)\s+[a-z0-9]+",
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

        clean = re.sub(r"^[#*_`>\s-]+|[#*_`\s]+$", "", s).strip()
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


def answer_parser(
    text: str,
    questions: list[dict],
    question_lines: list[int],
    explanations: bool,
) -> list[dict]:
    """
    Resolve each question's correct_index and optional explanation.

    Each answer pattern is tried independently. The first pattern that
    produces exactly one valid answer per question is used.

    Explanations are never captured by the answer regex. They are extracted
    as the text between the current answer line and whichever comes first:
      - the next answer line matched by the same pattern
      - the next question line
      - the end of the text
    """

    if len(question_lines) != len(questions):
        raise ValueError(
            f"Question line count ({len(question_lines)}) does not match "
            f"question count ({len(questions)})."
        )

    # Character offset of the beginning of each line.
    line_starts = [0]

    for line in text.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))

    best_matches = []

    for pattern in ANSWER_PATTERNS:
        answer_matches = list(
            re.finditer(
                pattern,
                text,
                re.IGNORECASE | re.MULTILINE,
            )
        )

        matches = [match.group(1).upper() for match in answer_matches]

        if len(matches) > len(best_matches):
            best_matches = matches

        # This pattern must match exactly one answer per question.
        if len(answer_matches) != len(questions):
            continue

        # Validate that every matched answer exists in its question's
        # options.
        valid = True

        for q, letter in zip(questions, matches):
            correct_index = ord(letter) - ord("A")

            if correct_index < 0 or correct_index >= len(q["options"]):
                valid = False
                break

        if not valid:
            continue

        # Get the line number where each answer starts.
        answer_lines = [text.count("\n", 0, match.start()) for match in answer_matches]

        for i, (q, answer_match, answer_line) in enumerate(
            zip(questions, answer_matches, answer_lines)
        ):
            q["correct_index"] = ord(answer_match.group(1).upper()) - ord("A")

            if not explanations:
                continue

            # The next question always starts at the beginning of its line.
            next_question_line = (
                question_lines[i + 1] if i + 1 < len(question_lines) else None
            )

            next_question_pos = (
                line_starts[next_question_line]
                if next_question_line is not None
                else None
            )

            # The next answer normally starts on its own line, but it might
            # be on the same line as the current answer. Therefore, use the
            # actual character position of the next answer instead of its line.
            next_answer_pos = (
                answer_matches[i + 1].start() if i + 1 < len(answer_matches) else None
            )

            # Find the closest boundary after the current answer.
            possible_end_positions = [
                pos
                for pos in (next_question_pos, next_answer_pos)
                if pos is not None and pos > answer_match.end()
            ]

            if possible_end_positions:
                # Stop immediately before whichever comes first.
                end = min(possible_end_positions)
            else:
                # Nothing follows this answer.
                end = len(text)

            # Start immediately after the current answer.
            start = answer_match.end()

            explanation = text[start:end].strip()
            # If this is the last answer in an answer key, don't consume
            # unrelated text after the explanation.
            is_last_answer = i == len(answer_matches) - 1

            if is_last_answer:
                explanation = re.split(
                    r"\n\s*\n",
                    explanation,
                    maxsplit=1,
                )[0].strip()

            if explanation:
                explanation = clean_explanation(explanation)

                # Only add the explanation if cleanup left actual text.
                if explanation:
                    q["explanation"] = explanation

        return questions

    raise ValueError(
        "Failed to parse quiz:\n"
        "Did the message make a formatting mistake? If not, "
        "consider telling the LLM to use the tool and submitting a bug report.\n"
        f"Questions: {len(questions)}.\n"
        f"Answers found: {len(best_matches)}.\n"
        f"Closest answers: {best_matches}.\n"
    )


# =========================================================
# HELPERS
# =========================================================


def clean_text(text: str, strip_refs: bool, strip_end_brackets: bool):
    """
    Remove thinking blocks and reference links,
    and convert markdown links and embedded images to HTML.
    Code spans and fenced code blocks are protected from processing.
    """

    protected_parts = []

    def protect(match):
        protected_parts.append(match.group(0))
        return f"\ue000{len(protected_parts) - 1}\ue001"

    # Delete reasoning/tool-call blocks entirely (tag + body)
    text = re.sub(
        r'<details\s+type=["\'](?:reasoning|tool_calls)["\'][^<>]*>.*?</details>',
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # For any remaining <details>, unwrap them.
    text = re.sub(
        r"<summary>.*?</summary>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"</?details[^<>\n]*>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Protect fenced code blocks first.
    text = re.sub(
        r"```[\s\S]*?```",
        protect,
        text,
    )

    # Protect inline code spans.
    text = re.sub(
        r"`[^`\n]*`",
        protect,
        text,
    )

    # Remove reference-style link definitions: [id]: url
    if strip_refs:
        text = re.sub(
            r"\s*\[\d+\](?!.*[^\W\d_])",
            "",
            text,
            flags=re.MULTILINE,
        )

    # Remove answer/hint brackets at the end.
    if strip_end_brackets:
        text = re.sub(
            r"\s*\[[^\]]*\](?=[^\W\d_]*$)",
            "",
            text,
            flags=re.MULTILINE,
        )

    # Convert Markdown images to HTML images.
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        r'<img src="\2" alt="\1">',
        text,
    )

    # Convert Markdown links to HTML links.
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        text,
    )

    # Restore protected code.
    text = re.sub(
        r"\uE000(\d+)\uE001",
        lambda m: protected_parts[int(m.group(1))],
        text,
    )

    return text.strip().replace("\r", "")


def _remove_unmatched_delimiters(text: str) -> str:
    """Remove unmatched (), [], {} delimiters without touching valid pairs."""
    pairs = {")": "(", "]": "[", "}": "{"}
    openings = set(pairs.values())

    stack: list[tuple[str, int]] = []
    remove: set[int] = set()

    for i, char in enumerate(text):
        if char in openings:
            stack.append((char, i))

        elif char in pairs:
            if stack and stack[-1][0] == pairs[char]:
                stack.pop()
            else:
                remove.add(i)

    # Anything left open was unmatched.
    remove.update(i for _, i in stack)

    if not remove:
        return text

    return "".join(char for i, char in enumerate(text) if i not in remove)


def _remove_unmatched_bold(text: str) -> str:
    """
    Remove unmatched ** markers.

    IMPORTANT:
    Single '*' is never touched, because it may be valid Markdown
    such as *Why:*.
    """
    markers = list(re.finditer(r"\*\*", text))

    if len(markers) % 2 == 0:
        return text

    # Pair markers from left to right. The final marker is unmatched.
    marker = markers[-1]

    return text[: marker.start()] + text[marker.end() :]


def _normalize_bullet(text: str) -> str:
    """
    Convert a malformed Markdown bullet:

        * *Why:* Venus...

    into:

        - *Why:* Venus...

    The *Why:* emphasis is preserved.
    """
    return re.sub(
        r"(?m)^([ \t]*)\*[ \t]+(\*[^*\r\n]+\*)",
        r"\1- \2",
        text,
    )


def clean_explanation(text: str) -> str:
    text = text.strip()

    while True:
        previous = text

        # Remove terminal punctuation temporarily so wrappers
        body = text
        suffix = ""

        while body and body[-1] in ".!?;:":
            suffix = body[-1] + suffix
            body = body[:-1].rstrip()

        # Remove obvious artifacts at the outermost beginning.
        body = re.sub(
            r"^(?:\*\*|[,)\]}>|]+)\s*",
            "",
            body,
        ).strip()

        # Remove wrappers ONLY when they surround the entire remaining text
        wrappers = (
            ('"', '"'),
            ("(", ")"),
            ("[", "]"),
            ("{", "}"),
            ("**", "**"),
        )

        for opening, closing in wrappers:
            if (
                len(body) >= len(opening) + len(closing)
                and body.startswith(opening)
                and body.endswith(closing)
            ):
                body = body[len(opening) : -len(closing)].strip()
                break

        text = body + suffix

        # Remove unmatched brackets anywhere in the text.
        cleaned = _remove_unmatched_delimiters(text)

        if cleaned != text:
            text = cleaned
            continue

        # Remove unmatched ** anywhere in the text.
        cleaned = _remove_unmatched_bold(text)

        if cleaned != text:
            text = cleaned
            continue

        # Normalize malformed Markdown bullets.
        cleaned = _normalize_bullet(text)

        if cleaned != text:
            text = cleaned
            continue

        # Nothing changed -> all recursive cleanup is finished.
        if text == previous:
            break

    # Remove a trailing Markdown table delimiter.
    text = re.sub(r"\s*\|\s*$", "", text).strip()

    # Add terminal punctuation.
    lines = []

    for line in text.splitlines():
        line = line.rstrip()

        if line and line[-1] not in ".!?;:)]}":
            line += "."

        lines.append(line)

    # If nothing but punctuation/whitespace remains, there is no explanation.
    if not re.search(r"[^\W_]", text, re.UNICODE):
        return ""

    return "\n".join(lines).strip()


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


def wrap_html(
    quiz, enable_mathjax: bool, light_theme="default_light", dark_theme="default_dark"
):
    return "__HTML_PLACEHOLDER__"
