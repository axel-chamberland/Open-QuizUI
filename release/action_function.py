import json

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
    payload = {"enableMathJax": bool(enable_mathjax), "quiz": quiz}

    app_data = json.dumps(payload, ensure_ascii=False)

    return (
        HTML_TEMPLATE
        .replace("__APP_DATA__", app_data)
        .replace("__LIGHT_THEME__", light_theme)
        .replace("__DARK_THEME__", dark_theme)
    )


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title id="page-title">Open-QuizUI</title>

    <link rel="icon" href="https://raw.githubusercontent.com/axel-chamberland/Open-QuizUI/main/src/openquizui/action_logo.svg">

    <style>
:root {
    color-scheme: light dark;
    __LIGHT_THEME__
}

@media (prefers-color-scheme: dark) {
    :root {
        __DARK_THEME__
    }
}
</style>
    <style>
.app-loading {
    visibility: hidden;
}

* {
    box-sizing: border-box;
    font-family: inherit;
}

body {
    background: var(--bg);
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    align-items: center;
    margin: 0;
}

:is(:fullscreen, .pseudo-fullscreen-active) body {
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
}

:is(:fullscreen, .pseudo-fullscreen-active) .question-box,
:is(:fullscreen, .pseudo-fullscreen-active) #results,
:is(:fullscreen, .pseudo-fullscreen-active) #editor {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}

:is(:fullscreen, .pseudo-fullscreen-active) .navigation-scroll {
    flex: 0 0 auto;
    order: 1;
}

.title-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}

.title-bar h1 {
    margin: 0;
}

.question-box,
#results,
#editor {
    display: flex;
    flex-direction: column;
    color: var(--text);
    width: min(800px, 100%);
    padding: 8px;
    height: auto;
}

#question {
    margin-bottom: 2em;
    font-size: 1.1rem;
}

#question-scroll {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    min-height: 0;
}

:is(:fullscreen, .pseudo-fullscreen-active) #question-scroll {
    flex: 1;
    order: 0;
}

#options {
    display: grid;
    grid-template-columns: 1;
    max-width: 100%;
    gap: 0.75rem;
}

:is(:fullscreen, .pseudo-fullscreen-active) #options {
    flex: 1;
    min-height: 0;
}

button {
    border: 1px solid;
    border-radius: 0.25rem;
    border-color: var(--border);
    background: var(--btn);
    cursor: pointer;
    text-align: center;
    color: var(--text);
    font-size: 1.1em;
}

button svg {
    width: 1em;
    height: 1em;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.option {
    padding: 1rem 3rem 1rem 3rem;
    position: relative;
    text-align: center;
}

button:disabled {
    opacity: 0.4;
}

.option:hover {
    filter: contrast(1.1);
}

.option.correct {
    background: var(--correct_bg);
    border-color: var(--success);
    opacity: 1;
}

.option.wrong {
    background: var(--wrong_bg);
    border-color: var(--danger);
    opacity: 1;
}


.option::after {
    position: absolute;
    right: 1rem;
    top: 50%;
    transform: translateY(-50%);
    width: 1rem;
    text-align: center;
}

.option.correct::after {
    content: " ✓";
    font-weight: bold;
}

.option.wrong::after {
    content: " ✗";
    font-weight: bold;
}

#explanation {
    display: none;
    margin-top: 1rem;
    padding: 0.75rem;
    background: var(--btn);
    border-radius: 0.5rem;
}

.navigation-scroll {
    overflow-x: auto;
    overflow-y: hidden;
}

#navigation,
#results-navigation,
#editor-navigation {

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
}

#navigation button,
#results-navigation button,
#editor-navigation button {
    font-size: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

:is(:fullscreen, .pseudo-fullscreen-active) #navigation,
:is(:fullscreen, .pseudo-fullscreen-active) #results-navigation,
:is(:fullscreen, .pseudo-fullscreen-active) #editor-navigation {
    margin: 0;
    border: 0;
}

#navigation button,
#results-navigation button,
#editor-navigation button {
    font-size: 2rem;


}

#reveal-button,
#maximize-button,
#download-button,
#question-selector {
    flex: 0 0 auto;
    min-width: 2rem;
}


#prev-button,
#next-button {
    flex: 1;
    font-size: clamp(1.5rem, 5vw, 2rem);
    max-width: 4rem;
}

#question-selector {
    display: flex;
    align-items: center;
    white-space: nowrap;

    background: var(--btn);
    color: var(--text);

    border: 1px solid var(--border);
    border-radius: 0.25rem;

    font-size: 1.1rem;

    gap: 0.2rem;


}


#question-number {

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

}


#question-number:focus {
    outline: none;
    border: none;
}

#question-count {
    margin-right: 0.3em;
}

mjx-container {
    max-width: 100%;
    overflow-x: auto;
    white-space: normal;
}

/* Hide timer by default */
#timer {
    display: none;
    min-width: 4rem;
    font-size: 1.1rem;
    text-align: center;
    font-variant-numeric: tabular-nums;
}

#timer.visible {
    display: inline-block;
}

#correct {
    color: var(--success);
}

#wrong {
    color: var(--danger);
}

#unanswered {
    color: var(--unanswered);
}

#skipped {
    color: var(--skipped);
}

.chart-correct {
    stroke: var(--success);
}

.chart-wrong {
    stroke: var(--danger);
}

.chart-unanswered {
    stroke: var(--unanswered);
}

.chart-skipped {
    stroke: var(--skipped);
}


#results-scroll {
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin: 0 auto;
    text-align: center;
    overflow-y: auto;
}

/* When embedded in an iframe */
body.embedded #results-scroll {
    max-height: 600px;
}

:is(:fullscreen, .pseudo-fullscreen-active) #results-scroll {
    flex: 1;
    min-height: 0;
    max-height: none !important;
    padding: 1rem;
    box-sizing: border-box;
}

.stat-row {
    display: flex;
    gap: 1rem;
}

.stat-row>div {
    flex: 1;
    padding: 0.5rem;
    border-radius: 0.5rem;
    background: var(--btn);
}

#statsChart {
    height: min(50vh, 500px);
    align-self: center;
}

.correction-sheet {
    border-top: 1px solid var(--border);
    text-align: left;
}

.correction-sheet article {
    padding: 1rem 0;
    border-bottom: 1px solid var(--border);
}

.correction-sheet h2 {
    margin-bottom: 1rem;
}

.correction-sheet h3 {
    margin-top: 0;
}

.correction-sheet p {
    margin: 0.5rem 0;
}


:is(:fullscreen, .pseudo-fullscreen-active) #editor {
    flex: 1;
    min-height: 0;
}


#editor-scroll {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    min-height: 0;
}

:is(:fullscreen, .pseudo-fullscreen-active) #editor-scroll {
    flex: 1;
    min-height: 0;
    order: 0;
    padding: 1rem;
    box-sizing: border-box;
}

textarea {
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: 1em;
    field-sizing: content;
}

textarea:focus {
    outline: none;
    border-color: var(--success);
}

#editor-distractors article {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
}

#editor-distractors textarea {
    width: 80%;
    height: auto;
}

#editor-distractors .delete-prompt {
    display: none;
}


.editor-prompt {
    display: none;
}

.editor-prompt.visible {
    display: block;
}

.editor-prompt .button-row {
    display: flex;
    gap: 0.5rem;
}

.answer-position {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.answer-position p {
    margin: 0.5rem 0;
}

.answer-position input {
    width: 3ch;
    field-sizing: content;

    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: 1em;
    text-align: center;
}


/* image and embedded styles */
img,
video,
iframe,
table {
    display: block;
    max-width: 100%;
    object-fit: contain;
    margin-inline: auto;
}

</style>
</head>

<body class="app-loading">
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
        <rect x="5" y="4" width="14" height="17" rx="2"/>
        <path d="M9 3h6v3H9z"/>
        <path d="M8 11h8M8 15h5"/>
    </symbol>

    <symbol id="icon-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </symbol>

    <symbol id="icon-copy-all" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
        <polyline points="2 17 12 22 22 17"></polyline>
        <polyline points="2 12 12 17 22 12"></polyline>
    </symbol>

    <symbol id="icon-save" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
        <polyline points="17 21 17 13 7 13 7 21"></polyline>
        <polyline points="7 3 7 8 15 8"></polyline>
    </symbol>

    <symbol id="icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
    </symbol>
</svg>

<div class="question-box">
    <div class="title-bar">
        <h1 id="title">Open-QuizUI</h1>
        <span id="timer">00:00</span>
    </div>
    <div class="navigation-scroll">

    <div id="navigation">

        <button id="prev-button" aria-label="Previous question">&lt;</button>

        <div id="question-selector">
            <input id="question-number" type="text" inputmode="numeric" value="1">
            <span class="separator">/</span>
            <span id="question-count">1</span>
        </div>

        <button id="next-button" aria-label="Next question">&gt;</button>

        <button id="reveal-button" title="Reveal answer" aria-label="Reveal answer">
            <svg><use href="#icon-reveal"></use></svg>
        </button>

        <button id="maximize-button" title="Toggle Fullscreen" aria-label="Fullscreen">
            <svg><use href="#icon-fullscreen"></use></svg>
        </button>

        <button id="download-button" title="Download quiz" aria-label="Download quiz">
            <svg><use href="#icon-download"></use></svg>
        </button>

        <button id="timer-toggle" title="Toggle timer" aria-label="Toggle timer">
            <svg><use href="#icon-timer"></use></svg>
        </button>

        <button id="copy-all-button" title="Copy quiz" aria-label="Copy quiz">
            <svg><use href="#icon-copy-all"></use></svg>
        </button>

        <button id="copy-question-button" title="Copy question" aria-label="Copy question">
            <svg><use href="#icon-copy"></use></svg>
        </button>
        <button id="editor-button" title="Edit question" aria-label="Edit question">
            <svg><use href="#icon-editor"></use></svg>
        </button>

    </div>
    </div>
    <div id="question-scroll">
        <p id="question"></p>
        <div id="options"></div>
        <div id="explanation"></div>
    </div>
</div>


<div id="results" style="display: none;">
    <div class=navigation-scroll>
        <div id="results-navigation">
            <button id="results-back-button" title="Back to quiz" aria-label="Back to quiz">&lt;</button>

            <button id="results-maximize-button" title="Toggle Fullscreen" aria-label="Fullscreen">
                <svg><use href="#icon-fullscreen"></use></svg>
            </button>

            <button id="results-download-button" title="Download quiz" aria-label="Download quiz">
                <svg><use href="#icon-download"></use></svg>
            </button>

            <button id="results-copy-all-button" title="Copy quiz" aria-label="Copy quiz">
                <svg><use href="#icon-copy-all"></use></svg>
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

        <button id="restart-button" aria-label="Restart quiz">Restart Quiz</button>
        <div id="restart-confirm" style="display: none;">
            <span>Restart quiz?</span>
            <button id="confirm-restart-button" aria-label="Confirm restart">Yes</button>
            <button id="cancel-restart-button" aria-label="Cancel restart">No</button>
        </div>

    <section class="correction-sheet">
        <h2>Correction</h2>
        <div id="question-corrections"></div>
    </section>
    </div>

</div>


<div id="editor" style="display: none;">
    <h1>Question Editor</h1>
    <div class="navigation-scroll" id="editor-navigation">
        <button id="editor-save-button" title="Save changes" aria-label="Save changes" data-tooltip="Save changes">
            <svg><use href="#icon-save"></use></svg>
        </button>
        <button title="Copy quiz" aria-label="Copy quiz">
            <svg><use href="#icon-copy-all"></use></svg>
        </button>
        <button id="editor-copy-button" title="Copy question" aria-label="Copy question">
            <svg><use href="#icon-copy"></use></svg>
        </button>
        <button id="editor-maximize-button" title="Fullscreen" aria-label="Fullscreen">
            <svg><use href="#icon-fullscreen"></use></svg>
        </button>
        <button id="editor-close-button" title="Close editor" aria-label="Close editor" data-tooltip="Close editor">
            <svg><use href="#icon-close"></use></svg>
        </button>
    </div>
    <div id="editor-close" class="editor-prompt">
        <p id="editor-prompt-message"></p>
        <div class="button-row">
            <button id="editor-prompt-yes">yes</button>
            <button id="editor-prompt-no">no</button>
        </div>
    </div>
    <p>
        <strong>Limitation:</strong>
        Changes are stored in your browser.<br>
        Download the modified quiz as a new HTML file to keep your changes permanently.
    </p>
    <div id="editor-scroll">
        <p><strong>Title:</strong></p>
        <div id="editor-title"></div>
        <p><strong>Question:</strong></p>
        <div id="editor-question"></div>
        <div class="answer-position">
            <p><strong>Answer Position:</strong></p>
            <input type="text" id="editor-answer-number" inputmode="numeric">        </div>
        <p><strong>Explanation:</strong></p>
        <div id="editor-explanation"></div>
        <p><strong>Choices:</strong></p>
        <div id="editor-distractors"></div>

    </div>
</div>

<script id="app-data" type="application/json">__APP_DATA__</script>

<script type="module">
// frontend/src/persistence/progress.js
function hashQuiz(quiz2) {
  const data = JSON.stringify(quiz2);
  let hash = 0;
  for (let i = 0; i < data.length; i++) {
    hash = (hash << 5) - hash + data.charCodeAt(i);
    hash |= 0;
  }
  return hash >>> 0;
}
function getProgressKey(quizStorageKey) {
  return `currentQuestionIndex_${quizStorageKey}`;
}
function getStoredQuestionIndex(quizStorageKey) {
  try {
    const index = Number(
      localStorage.getItem(getProgressKey(quizStorageKey))
    );
    if (!Number.isInteger(index)) {
      return 0;
    }
    return Math.max(0, Math.min(index, state.quiz.questions.length - 1));
  } catch {
    return 0;
  }
}
function setStoredQuestionIndex(quizStorageKey, value) {
  try {
    localStorage.setItem(
      getProgressKey(quizStorageKey),
      String(value)
    );
  } catch {
  }
}

// frontend/src/state.js
var UNANSWERED = 0;
var CORRECT = 1;
var WRONG = 2;
var SKIPPED = 3;
var state = {
  mathReady: false,
  quiz: null,
  wrongAnswerCount: 0,
  optionButtons: [],
  currentQuestion: null,
  answerRevealed: false,
  currentQuestionIndex: 0,
  questionResults: [],
  questionAnswers: [],
  defaultStartDate: Date.now(),
  quizStorageKey: null,
  timer: {
    visible: false,
    start: null,
    elapsed: 0,
    interval: null
  }
};
function initializeState(quiz2) {
  state.quiz = quiz2;
  state.quizStorageKey = hashQuiz(quiz2);
  state.currentQuestionIndex = getStoredQuestionIndex(state.quizStorageKey);
  state.currentQuestion = null;
  state.optionButtons = [];
  state.wrongAnswerCount = 0;
  state.answerRevealed = false;
  state.questionResults = new Array(quiz2.questions.length).fill(UNANSWERED);
  state.questionAnswers = new Array(quiz2.questions.length).fill(null);
  state.defaultStartDate = Date.now();
}

// frontend/src/shared/markdown.js
function renderMath(text, mathReady) {
  if (!text) return "";
  return text.replace(/\$(.+?)\$/g, (match, expr) => {
    if (mathReady) {
      return match;
    }
    return `<code>${expr}</code>`;
  });
}
function escapeHtml(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/'/g, "&#39;");
}
function renderMarkdown(text, mathReady) {
  if (!text) return "";
  const protectedParts = [];
  const BT = String.fromCharCode(96);
  function protect(value) {
    const index = protectedParts.length;
    protectedParts.push(value);
    return `\uE000${index}\uE001`;
  }
  const fence = BT + BT + BT;
  const fenceRegex = new RegExp(
    fence + "(?:[^\\n" + BT + "]*)\\n([\\s\\S]*?)" + fence,
    "g"
  );
  text = text.replace(
    fenceRegex,
    (_, content) => protect(`<pre><code>${escapeHtml(content)}</code></pre>`)
  );
  const inlineRegex = new RegExp(BT + "([^" + BT + "]*?)" + BT, "g");
  text = text.replace(
    inlineRegex,
    (_, content) => protect(`<code>${escapeHtml(content)}</code>`)
  );
  text = text.replace(/\$\$[\s\S]*?\$\$/g, protect);
  text = text.replace(/\$(?!\$)[\s\S]*?\$(?!\$)/g, protect);
  const voidElements = /* @__PURE__ */ new Set([
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr"
  ]);
  text = text.replace(
    /<\/?(\p{L}[\p{L}\p{N}-]*)(?:\s[^>]*)?>/gu,
    (match, tagName, offset, wholeText) => {
      const tag = tagName.toLowerCase();
      if (match.startsWith("</")) {
        return match;
      }
      if (/\/>$/.test(match)) {
        return match;
      }
      if (voidElements.has(tag)) {
        return match;
      }
      const closingTag = new RegExp(`</${tag}\\s*>`, "iu");
      if (closingTag.test(wholeText.slice(offset + match.length))) {
        return match;
      }
      return match.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
  );
  text = text.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>").replace(/\*(.*?)\*/g, "<i>$1</i>");
  text = text.replace(
    /\uE000(\d+)\uE001/g,
    (_, index) => protectedParts[Number(index)]
  );
  return renderMath(text, mathReady);
}

// frontend/src/rendering/mcq.js
function showExplanation(question) {
  const explanationEl = document.getElementById("explanation");
  if (question.explanation) {
    explanationEl.innerHTML = renderMarkdown(question.explanation, state.mathReady);
    explanationEl.style.display = "block";
    if (state.mathReady) {
      window.MathJax.typesetPromise([explanationEl]).catch(
        (err) => console.error("MathJax typesetting failed:", err)
      );
    }
  } else {
    explanationEl.innerHTML = "";
    explanationEl.style.display = "none";
  }
}
async function renderQuiz() {
  const questionBox = document.querySelector(".question-box");
  const questionText = questionBox.querySelector("#question");
  const optionsContainer = document.getElementById("options");
  const navigationContainer = questionBox.querySelector("#navigation");
  const explanationEl = document.getElementById("explanation");
  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    document.getElementById("question").textContent = "No valid questions parsed";
    return;
  }
  questionText.innerHTML = renderMarkdown(
    state.quiz.questions[state.currentQuestionIndex].question,
    state.mathReady
  );
  explanationEl.textContent = "";
  explanationEl.style.display = "none";
  optionsContainer.innerHTML = "";
  state.wrongAnswerCount = 0;
  state.optionButtons = [];
  state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion.options.forEach((option, index) => {
    const button = document.createElement("button");
    button.innerHTML = renderMarkdown(option, state.mathReady);
    button.className = "option";
    state.optionButtons.push(button);
    button.addEventListener("click", () => {
      handleAnswer(index, button);
    });
    optionsContainer.appendChild(button);
  });
  const prevButton = navigationContainer.querySelector("#prev-button");
  prevButton.disabled = state.currentQuestionIndex === 0;
  document.getElementById("question-scroll").scrollTop = 0;
  if (state.mathReady && window.MathJax) {
    try {
      await window.MathJax.typesetPromise();
    } catch (err) {
      console.error("MathJax typesetting failed:", err);
    }
  }
}

// frontend/src/persistence/stats.js
function getStatsKey(quizStorageKey) {
  return `quizStats_${quizStorageKey}`;
}
function loadStats() {
  try {
    const data = JSON.parse(localStorage.getItem(getStatsKey(state.quizStorageKey)));
    if (Array.isArray(data?.results)) {
      state.questionResults = data.results;
    }
    if (Array.isArray(data?.answers)) {
      state.questionAnswers = data.answers;
    }
    if (data?.startDate) {
      state.defaultStartDate = data.startDate;
    }
  } catch {
    state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
    state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
    state.defaultStartDate = Date.now();
  }
}
function saveStats() {
  try {
    localStorage.setItem(
      getStatsKey(state.quizStorageKey),
      JSON.stringify({
        results: state.questionResults,
        answers: state.questionAnswers,
        startDate: state.defaultStartDate
      })
    );
  } catch {
  }
}

// frontend/src/shared/formatting.js
function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}
function formatQuestionAsText(question, index) {
  const lines = [];
  lines.push(`Question ${index + 1}: ${question.question}`);
  lines.push("");
  question.options.forEach((option, i) => {
    const letter = String.fromCharCode(65 + i);
    lines.push(`${letter}. ${option}`);
  });
  return lines.join("\n");
}
function formatAnswerKey(questions) {
  const lines = [
    "Answer Key:",
    "",
    "| Question | Correct Answer | Explanation |",
    "| --- | --- | --- |"
  ];
  questions.forEach((question, index) => {
    const correctLetter = String.fromCharCode(65 + question.correct_index);
    const escapeTableCell = (text) => String(text ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
    lines.push(
      `| ${index + 1} | ${correctLetter} | ${escapeTableCell(question.explanation || "")} |`
    );
  });
  return lines.join("\n");
}
function formatQuizAsText(quiz2) {
  const lines = [quiz2.title, ""];
  quiz2.questions.forEach((question, index) => {
    lines.push(formatQuestionAsText(question, index));
    lines.push("");
  });
  lines.push(formatAnswerKey(quiz2.questions));
  return lines.join("\n").trim();
}

// frontend/src/timer.js
var timerElement = document.getElementById("timer");
function getTimerKey(quizStorageKey) {
  return `quizTimer_${quizStorageKey}`;
}
function loadTimer(state2) {
  try {
    const data = JSON.parse(localStorage.getItem(getTimerKey(state2.quizStorageKey)));
    state2.timer.elapsed = data?.elapsed || 0;
    state2.timer.start = data?.start || null;
  } catch {
    state2.timer.elapsed = 0;
    state2.timer.start = null;
  }
}
function saveTimer() {
  try {
    localStorage.setItem(
      getTimerKey(state.quizStorageKey),
      JSON.stringify({
        elapsed: state.timer.elapsed,
        start: state.timer.start
      })
    );
  } catch {
  }
}
function updateTimer() {
  if (!state.timer.start) return;
  const elapsed = state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1e3);
  timerElement.textContent = formatTime(elapsed);
}
function toggleTimer() {
  state.timer.visible = !state.timer.visible;
  timerElement.classList.toggle("visible", state.timer.visible);
  if (state.timer.visible) {
    loadTimer(state);
    if (!state.timer.start) {
      state.timer.start = Date.now();
      saveTimer();
    }
    updateTimer();
    state.timer.interval = setInterval(updateTimer, 1e3);
  } else {
    if (state.timer.start) {
      state.timer.elapsed += Math.floor((Date.now() - state.timer.start) / 1e3);
      state.timer.start = null;
      saveTimer();
    }
    clearInterval(state.timer.interval);
    state.timer.interval = null;
  }
}

// frontend/src/rendering/results.js
async function renderResults() {
  const questionBox = document.querySelector(".question-box");
  const results2 = document.getElementById("results");
  questionBox.style.display = "none";
  results2.style.display = "";
  const correct = state.questionResults.filter((x) => x === CORRECT).length;
  const wrong = state.questionResults.filter((x) => x === WRONG).length;
  const unanswered = state.questionResults.filter((x) => x === UNANSWERED).length;
  const skipped = state.questionResults.filter((x) => x === SKIPPED).length;
  const total = state.quiz.questions.length;
  const answered = correct + wrong;
  const accuracy = answered > 0 ? correct / answered * 100 : 0;
  const elapsed = state.timer.visible ? state.timer.elapsed + Math.floor((Date.now() - state.timer.start) / 1e3) : Math.floor((Date.now() - state.defaultStartDate) / 1e3);
  const chartData = {
    labels: ["Correct", "Wrong", "Unanswered", "Skipped"],
    datasets: [
      {
        label: "Score Chart",
        data: [correct, wrong, unanswered, skipped],
        classNames: [
          "chart-correct",
          "chart-wrong",
          "chart-unanswered",
          "chart-skipped"
        ]
      }
    ]
  };
  document.getElementById("score").textContent = `Score: ${correct}/${wrong + correct}`;
  document.getElementById("accuracy").textContent = `Accuracy: ${accuracy.toFixed(1)}%`;
  document.getElementById("correct").textContent = `Correct: ${correct}`;
  document.getElementById("wrong").textContent = `Wrong: ${wrong}`;
  document.getElementById("unanswered").textContent = `Unanswered: ${unanswered}`;
  document.getElementById("skipped").textContent = `Skipped: ${skipped}`;
  document.getElementById("time").textContent = `Time: ${formatTime(elapsed)}`;
  document.getElementById("averageTime").textContent = `Average time per question: ${formatTime(Math.floor(elapsed / total))}`;
  createDonutChart(document.getElementById("statsChart"), chartData);
  showCorrectionSheet();
  if (state.mathReady && window.MathJax) {
    try {
      await MathJax.typesetPromise([
        document.getElementById("question-corrections")
      ]);
    } catch (err) {
      console.error("MathJax typesetting failed:", err);
    }
  }
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
function showCorrectionSheet() {
  const container = document.getElementById("question-corrections");
  const questions = state.quiz.questions;
  container.innerHTML = "";
  for (let index = 0; index < questions.length; index++) {
    const question = questions[index];
    const correctAnswer = question.options[question.correct_index];
    const userIndex = state.questionAnswers[index];
    const userAnswer = state.questionResults[index] === SKIPPED ? "Skipped" : userIndex !== null ? question.options[userIndex] : "Unanswered";
    const article = document.createElement("article");
    article.innerHTML = `
<h3>Question ${index + 1}</h3>

<p>${renderMarkdown(question.question, state.mathReady)}</p>

<p>
    <strong>Your answer:</strong>
    ${renderMarkdown(userAnswer, state.mathReady)}
</p>

<p>
    <strong>Correct answer:</strong>
    ${renderMarkdown(correctAnswer, state.mathReady)}
</p>

${question.explanation ? `
<p>
    <strong>Explanation:</strong>
    ${renderMarkdown(question.explanation, state.mathReady)}
</p>
` : ""}
`;
    container.appendChild(article);
  }
}
var questionNumber = document.getElementById("question-number");
function restartQuiz() {
  state.currentQuestionIndex = 0;
  questionNumber.value = 1;
  state.answerRevealed = false;
  state.wrongAnswerCount = 0;
  state.questionResults = new Array(state.quiz.questions.length).fill(UNANSWERED);
  state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
  document.getElementById("question-corrections").innerHTML = "";
  clearInterval(state.timer.interval);
  state.timer.interval = null;
  state.timer.elapsed = 0;
  state.timer.start = state.timer.visible ? Date.now() : null;
  state.defaultStartDate = Date.now();
  const timerElement2 = document.getElementById("timer");
  if (state.timer.visible) {
    updateTimer();
    state.timer.interval = setInterval(updateTimer, 1e3);
  } else {
    timerElement2.textContent = formatTime(0);
  }
  saveTimer();
  setStoredQuestionIndex(state.quizStorageKey, 0);
  const results2 = document.getElementById("results");
  const questionBox = document.querySelector(".question-box");
  results2.style.display = "none";
  questionBox.style.display = "";
  document.getElementById("restart-confirm").style.display = "none";
  renderQuiz();
}

// frontend/src/quiz.js
var results = document.getElementById("results");
function nextQuestion() {
  if (state.currentQuestionIndex >= state.quiz.questions.length - 1 && results.style.display === "none") {
    renderResults();
    return;
  }
  goTo(state.currentQuestionIndex + 1);
}
function prevQuestion() {
  const results2 = document.getElementById("results");
  if (results2.style.display !== "none") {
    results2.style.display = "none";
    document.querySelector(".question-box").style.display = "";
    renderQuiz();
    return;
  }
  if (state.currentQuestionIndex <= 0) return;
  goTo(state.currentQuestionIndex - 1);
}
function goTo(question_index) {
  question_index = Math.max(
    0,
    Math.min(question_index, state.quiz.questions.length - 1)
  );
  state.currentQuestionIndex = question_index;
  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
  state.answerRevealed = false;
  const questionNumber2 = document.getElementById("question-number");
  questionNumber2.value = state.currentQuestionIndex + 1;
  renderQuiz();
}
function handleAnswer(index, button) {
  saveStats();
  if (index === state.currentQuestion.correct_index) {
    button.classList.add("correct");
    button.disabled = true;
    state.answerRevealed = true;
    if (state.wrongAnswerCount === 0) {
      state.questionResults[state.currentQuestionIndex] = CORRECT;
      state.questionAnswers[state.currentQuestionIndex] = index;
      saveStats();
    }
    state.optionButtons.forEach((btn) => btn.disabled = true);
    showExplanation(state.currentQuestion);
  } else {
    button.classList.add("wrong");
    button.disabled = true;
    state.questionResults[state.currentQuestionIndex] = WRONG;
    if (state.questionAnswers[state.currentQuestionIndex] === null) {
      state.questionAnswers[state.currentQuestionIndex] = index;
    }
    saveStats();
    state.wrongAnswerCount++;
    if (state.wrongAnswerCount === state.currentQuestion.options.length - 1) {
      revealAnswer();
    }
  }
}
function revealAnswer() {
  state.answerRevealed = true;
  if (state.questionResults[state.currentQuestionIndex] === UNANSWERED) {
    state.questionResults[state.currentQuestionIndex] = SKIPPED;
    saveStats();
  }
  state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
  const optionsContainer = document.getElementById("options");
  const buttons = optionsContainer.querySelectorAll("button");
  buttons[state.currentQuestion.correct_index].classList.add("correct");
  showExplanation(state.currentQuestion);
}
function setQuizTitle(title) {
  const displayTitle = title.slice(0, 60);
  document.title = displayTitle;
  document.getElementById("title").textContent = title;
}

// frontend/src/shared/download.js
function downloadQuizHTML() {
  const appData2 = {
    enableMathJax: state.mathReady,
    quiz: state.quiz
  };
  const filename = state.quiz.title;
  const documentClone = document.documentElement.cloneNode(true);
  const dataScript = documentClone.querySelector("#app-data");
  if (!dataScript) {
    throw new Error("Could not find #app-data");
  }
  dataScript.textContent = JSON.stringify(appData2, null, 2);
  const html = "<!DOCTYPE html>\n" + documentClone.outerHTML;
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".html") ? filename : filename + ".html";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// frontend/src/shared/clipboard.js
function copyQuestion() {
  const question = state.quiz.questions[state.currentQuestionIndex];
  const text = [
    formatQuestionAsText(question, state.currentQuestionIndex),
    "",
    formatAnswerKey([question])
  ].join("\n");
  copyToClipboard(text, "Question copied to clipboard.");
}
function copyQuiz() {
  copyToClipboard(formatQuizAsText(state.quiz), "Quiz copied to clipboard.");
}
async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
    }
  }
  return false;
}

// frontend/src/persistence/quiz_edits.js
function getQuizEditsKey(quizStorageKey) {
  return `quizEdits_${quizStorageKey}`;
}
function saveLocalEdit(index, titleChanged) {
  const key = getQuizEditsKey(state.quizStorageKey);
  let edits = {};
  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    edits = {};
  }
  if (titleChanged) {
    edits.title = state.quiz.title;
  }
  edits[index] = state.quiz.questions[index];
  try {
    localStorage.setItem(key, JSON.stringify(edits));
    console.log("Saved edit:", key, edits);
    return true;
  } catch (e) {
    console.error("Failed to save edit:", e);
    return false;
  }
}
function loadQuizEdits(state2) {
  const key = getQuizEditsKey(state2.quizStorageKey);
  try {
    const edits = JSON.parse(localStorage.getItem(key));
    if (!edits) {
      return;
    }
    if (edits.title !== void 0) {
      state2.quiz.title = edits.title;
    }
    for (const [index, question] of Object.entries(edits)) {
      const i = Number(index);
      if (Number.isInteger(i) && i >= 0 && i < state2.quiz.questions.length) {
        state2.quiz.questions[i] = question;
      }
    }
  } catch (e) {
    console.error("Failed to load quiz edits:", e);
  }
}

// frontend/src/rendering/editor.js
document.getElementById("editor-answer-number").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/\D/g, "");
});
function confirmRestart() {
  document.getElementById("restart-confirm").style.display = "flex";
}
function cancelRestart() {
  document.getElementById("restart-confirm").style.display = "none";
}
function openEditor() {
  const questionBox = document.querySelector(".question-box");
  const editor = document.getElementById("editor");
  const prompt = document.getElementById("editor-close");
  prompt.classList.remove("visible");
  questionBox.style.display = "none";
  editor.style.display = "";
  const titleField = document.getElementById("editor-title");
  const questionField = document.getElementById("editor-question");
  const explanationField = document.getElementById("editor-explanation");
  const editorAnswer = document.getElementById("editor-answer-number");
  const optionsContainer = document.getElementById("editor-distractors");
  const question = state.quiz.questions[state.currentQuestionIndex];
  titleField.innerHTML = `<textarea></textarea>`;
  titleField.querySelector("textarea").value = state.quiz.title;
  questionField.innerHTML = `<textarea></textarea>`;
  questionField.querySelector("textarea").value = question.question;
  explanationField.innerHTML = `<textarea></textarea>`;
  explanationField.querySelector("textarea").value = question.explanation || "";
  editorAnswer.value = question.correct_index + 1;
  optionsContainer.innerHTML = "";
  question.options.forEach((option) => {
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
  deleteBtn.textContent = "\u2326";
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
function showEditorPrompt(message, onYes = null, onNo = null, yesText = "yes", noText = "no") {
  const prompt = document.getElementById("editor-close");
  const messageElement = document.getElementById("editor-prompt-message");
  const yesButton = document.getElementById("editor-prompt-yes");
  const noButton = document.getElementById("editor-prompt-no");
  messageElement.textContent = message;
  yesButton.textContent = yesText;
  noButton.textContent = noText;
  yesButton.style.display = "";
  noButton.style.display = "";
  yesButton.onclick = () => {
    prompt.classList.remove("visible");
    if (onYes) onYes();
  };
  noButton.onclick = () => {
    prompt.classList.remove("visible");
    if (onNo) onNo();
  };
  prompt.classList.add("visible");
}
function showEditorAlert(message) {
  const prompt = document.getElementById("editor-close");
  const messageElement = document.getElementById("editor-prompt-message");
  const yesButton = document.getElementById("editor-prompt-yes");
  const noButton = document.getElementById("editor-prompt-no");
  messageElement.textContent = message;
  yesButton.textContent = "OK";
  yesButton.style.display = "";
  noButton.style.display = "none";
  yesButton.onclick = () => {
    prompt.classList.remove("visible");
  };
  prompt.classList.add("visible");
}
function validateAnswerIndex() {
  const answerInput = document.querySelector("#editor-answer-number");
  const val = parseInt(answerInput.value) - 1;
  const optionsContainer = document.getElementById("editor-distractors");
  const options = optionsContainer.querySelectorAll("article");
  if (val < 0 || val >= options.length) {
    answerInput.classList.add("input-error");
    showEditorAlert("Invalid Index: The selected option no longer exists.");
    return false;
  }
  return true;
}
function closeEditorConfirm() {
  showEditorPrompt(
    "Exit? Unsaved changes will be lost.",
    closeEditor,
    null,
    "yes",
    "no"
  );
}
function saveEdit() {
  if (!validateAnswerIndex()) {
    return;
  }
  const newTitleText = document.querySelector("#editor-title textarea").value;
  const newQuestionText = document.querySelector(
    "#editor-question textarea"
  ).value;
  const newIndex = parseInt(document.querySelector("#editor-answer-number").value) - 1;
  const optionsContainer = document.getElementById("editor-distractors");
  const updatedOptions = Array.from(
    optionsContainer.querySelectorAll("textarea")
  ).map((ta) => ta.value);
  const newExplanationText = document.querySelector(
    "#editor-explanation textarea"
  ).value;
  const titleChanged = state.quiz.title !== newTitleText;
  state.quiz.title = newTitleText;
  setQuizTitle(state.quiz.title);
  state.quiz.questions[state.currentQuestionIndex].question = newQuestionText;
  state.quiz.questions[state.currentQuestionIndex].correct_index = newIndex;
  state.quiz.questions[state.currentQuestionIndex].options = updatedOptions;
  state.quiz.questions[state.currentQuestionIndex].explanation = newExplanationText;
  if (saveLocalEdit(state.currentQuestionIndex, titleChanged)) {
    showEditorAlert("Changes saved.");
  }
}
function closeEditor() {
  const questionBox = document.querySelector(".question-box");
  const editor = document.getElementById("editor");
  const prompt = document.getElementById("editor-close");
  prompt.classList.remove("visible");
  editor.style.display = "none";
  const options = document.getElementById("editor-distractors");
  options.innerHTML = "";
  questionBox.style.display = "";
  renderQuiz();
}

// frontend/src/ui/fullscreen.js
var pseudoFullscreenState = null;
async function toggleFullscreen() {
  if (document.fullscreenElement || document.webkitFullscreenElement) {
    if (document.exitFullscreen) await document.exitFullscreen();
    else document.webkitExitFullscreen?.();
    return;
  }
  if (document.documentElement.classList.contains("pseudo-fullscreen-active")) {
    document.documentElement.classList.remove("pseudo-fullscreen-active");
    exitPseudoFullscreen();
    return;
  }
  const root = document.documentElement;
  if (root.requestFullscreen) {
    try {
      await root.requestFullscreen();
      return;
    } catch {
    }
  } else if (root.webkitRequestFullscreen) {
    root.webkitRequestFullscreen();
    return;
  }
  document.documentElement.classList.add("pseudo-fullscreen-active");
  enterPseudoFullscreen();
}
function enterPseudoFullscreen() {
  const iframe = window.frameElement;
  const topBody = window.top.document.body;
  topBody.classList.add("pseudo-fullscreen-active");
  pseudoFullscreenState = {
    scrollX: window.top.scrollX,
    scrollY: window.top.scrollY,
    elements: []
  };
  let el = iframe;
  while (el && el !== document.body) {
    pseudoFullscreenState.elements.push({
      el,
      style: el.getAttribute("style"),
      siblings: [...el.parentElement.children].filter((x) => x !== el).map((x) => [x, x.style.display])
    });
    el.style.position = "fixed";
    el.style.inset = "0";
    el.style.width = "100vw";
    el.style.height = "100dvh";
    el.style.margin = "0";
    el.style.maxWidth = "none";
    el.style.maxHeight = "none";
    el.style.zIndex = "999999";
    for (const child of el.parentElement.children) {
      if (child !== el) child.style.display = "none";
    }
    el = el.parentElement;
  }
}
function exitPseudoFullscreen() {
  const topBody = window.top.document.body;
  topBody.classList.remove("pseudo-fullscreen-active");
  if (!pseudoFullscreenState) {
    return;
  }
  const { elements, scrollX, scrollY } = pseudoFullscreenState;
  for (const item of elements) {
    if (item.style === null) item.el.removeAttribute("style");
    else item.el.setAttribute("style", item.style);
    for (const [sibling, display] of item.siblings)
      sibling.style.display = display;
  }
  pseudoFullscreenState = null;
  window.top.scrollTo(scrollX, scrollY);
  window.frameElement.scrollIntoView({
    block: "center",
    inline: "nearest"
  });
}

// frontend/src/ui/events.js
function initializeEvents() {
  document.getElementById("prev-button").addEventListener("click", prevQuestion);
  document.getElementById("next-button").addEventListener("click", nextQuestion);
  document.getElementById("reveal-button").addEventListener("click", revealAnswer);
  document.getElementById("maximize-button").addEventListener("click", toggleFullscreen);
  document.getElementById("download-button").addEventListener("click", downloadQuizHTML);
  document.getElementById("timer-toggle").addEventListener("click", toggleTimer);
  document.getElementById("copy-all-button").addEventListener("click", copyQuiz);
  document.getElementById("copy-question-button").addEventListener("click", copyQuestion);
  document.getElementById("editor-button").addEventListener("click", openEditor);
  document.getElementById("results-back-button").addEventListener("click", prevQuestion);
  document.getElementById("results-maximize-button").addEventListener("click", toggleFullscreen);
  document.getElementById("results-download-button").addEventListener("click", downloadQuizHTML);
  document.getElementById("results-copy-all-button").addEventListener("click", copyQuiz);
  document.getElementById("restart-button").addEventListener("click", confirmRestart);
  document.getElementById("confirm-restart-button").addEventListener("click", restartQuiz);
  document.getElementById("cancel-restart-button").addEventListener("click", cancelRestart);
  document.getElementById("editor-save-button").addEventListener("click", saveEdit);
  document.getElementById("editor-copy-button").addEventListener("click", copyQuestion);
  document.getElementById("editor-maximize-button").addEventListener("click", toggleFullscreen);
  document.getElementById("editor-close-button").addEventListener("click", closeEditorConfirm);
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    const key = e.key.toLowerCase();
    let index = -1;
    if (/^[1-9]$/.test(key)) {
      index = Number(key) - 1;
    }
    if (index >= 0 && index < state.optionButtons.length) {
      const button = state.optionButtons[index];
      if (!button.disabled) {
        handleAnswer(index, button);
      }
      return;
    }
    if (key === "enter" || key == " ") {
      e.preventDefault();
      if (!state.answerRevealed) {
        revealAnswer();
      } else {
        nextQuestion();
      }
      return;
    }
    if (key === "arrowright" || key === "l") {
      e.preventDefault();
      nextQuestion();
      return;
    }
    if (key === "arrowleft" || key === "h") {
      e.preventDefault();
      prevQuestion();
      return;
    }
  });
  const questionBox = document.querySelector(".question-box");
  questionBox.addEventListener("click", (e) => {
    if (e.target.closest("button, input")) return;
    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) return;
    const rect = questionBox.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x > rect.width * 0.7) {
      if (!state.answerRevealed) {
        revealAnswer();
      } else {
        nextQuestion();
      }
    } else if (x < rect.width * 0.3) {
      prevQuestion();
    }
  });
  const questionSelector = document.getElementById("question-selector");
  const questionNumber2 = document.getElementById("question-number");
  questionSelector.addEventListener("click", () => {
    questionNumber2.focus();
    questionNumber2.select();
  });
  questionNumber2.addEventListener("input", () => {
    questionNumber2.value = questionNumber2.value.replace(/\D/g, "");
  });
  questionNumber2.addEventListener("change", () => {
    if (!questionNumber2.value) return;
    goTo(Number(questionNumber2.value) - 1);
  });
}

// frontend/src/shared/mathjax.js
function loadMathJax(enabled) {
  if (!enabled) {
    state.mathReady = false;
    Promise.resolve(false);
    return;
  }
  window.MathJax = {
    tex: {
      inlineMath: [
        ["$", "$"],
        ["\\(", "\\)"]
      ]
    }
  };
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
    script.onload = () => {
      state.mathReady = true;
      resolve(true);
    };
    script.onerror = () => {
      state.mathReady = false;
      resolve(false);
    };
    document.head.appendChild(script);
  });
}

// frontend/src/ui/reportHeight.js
function reportHeight() {
  if (document.fullscreenElement || document.documentElement.classList.contains("pseudo-fullscreen-active")) return;
  const questionBox = document.querySelector(".question-box");
  const results2 = document.getElementById("results");
  const editor = document.getElementById("editor");
  const visible = questionBox.style.display !== "none" ? questionBox : results2.style.display !== "none" ? results2 : editor;
  const h = visible.scrollHeight;
  parent.postMessage({ type: "iframe:height", height: h }, "*");
}
function initHeightReporting() {
  window.addEventListener("load", () => {
    reportHeight();
    new ResizeObserver(reportHeight).observe(document.body);
  });
}

// frontend/src/main.js
var appData = JSON.parse(
  document.getElementById("app-data").textContent
);
var ENABLE_MATHJAX = appData.enableMathJax;
var quiz = appData.quiz;
try {
  if (window.top.document.body.classList.contains("pseudo-fullscreen-active")) {
    window.top.location.reload();
  }
} catch {
}
document.title = quiz.title.slice(0, 60);
initializeState(quiz);
loadStats();
loadQuizEdits(state);
var questionCount = document.getElementById("question-count");
questionCount.textContent = quiz.questions.length;
async function initializeQuiz() {
  await loadMathJax(ENABLE_MATHJAX);
  if (state.mathReady && window.MathJax?.startup?.promise) {
    await window.MathJax.startup.promise;
  }
  renderQuiz();
  initializeEvents();
  initHeightReporting();
}
if (document.readyState === "loading") {
  window.addEventListener("load", initializeQuiz, { once: true });
} else {
  initializeQuiz();
  document.body.classList.remove("app-loading");
}
export {
  ENABLE_MATHJAX,
  quiz
};

</script>

</body>
</html>
"""
