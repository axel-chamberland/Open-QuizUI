"""
title: QuizUI
author: Axel Chamberland
git_url: https://github.com/axel-chamberland/OpenQuizUI
description: This tool allows large language models to generated interactive multiple-choice quizzes.
version: 2.2.1
licence: MIT
"""

import random
import re
from functools import wraps
from textwrap import dedent
from typing import Literal

import markdown
import regex
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

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


class Tools:
    class Valves(BaseModel):
        shuffle_choices: bool = Field(
            default=True,
            description="Shuffle the order of choices",
        )
        enable_mathjax: bool = Field(
            default=False,
            description=(
                "Disabled by default for privacy. Enable LaTeX/math rendering with MathJax."
                "Requires Internet access to load the MathJax library from a CDN. When disabled or"
                "offline, LaTeX expressions are displayed as plain text."
            ),
        )
        enable_explanations: bool = Field(
            default=False,
            description=(
                "Instructs the model to include an explanations for each question."
                "Disabled by default as it requires the models to generate extra content."
            ),
        )

        quiz_mode: Literal["multiple-choice questions", "flashcards"] = Field(
            default="multiple-choice questions",
            description=(
                "Multiple-choice questions: users can toggle between MCQ "
                "and flashcards using the same questions. "
                "Flashcards: the model concentrates on generating flashcards "
                "(no MCQ toggle)."
            ),
        )

        theme_mode: Literal["browser", "light", "dark"] = Field(
            default="browser",
        )

        light_theme: Literal[tuple(THEMES)] = Field(
            default="default_light",
            description=(
                "Change the light mode theme. "
                "To define a new theme, add it to the THEMES dictionary at the top of the code. "
            ),
        )
        dark_theme: Literal[tuple(THEMES)] = Field(
            default="default_dark",
            description=(
                "Change the dark mode theme. "
                "To define a new theme, add it to the THEMES dictionary at the top of the code. "
            ),
        )
        prevent_reference_shuffle: bool = Field(
            default=True,
            description=(
                "Prevent shuffling choices when a choice refers to another "
                "answer choice's position or it is a true/false question."
            ),
        )
        choice_reference_patterns: str = Field(
            default="",
            description=(
                "Additional regex patterns for detecting when a choice should not be shuffled. "
                "Separate multiple patterns with |."
            ),
        )

    def __init__(self):
        self.valves = self.Valves()

    # This function adds to the docstring of generate_quiz for extra optional instructions
    def __getattribute__(self, name):
        if name == "generate_quiz":
            original = object.__getattribute__(
                self, "generate_quiz"
            )  # same name, no recursion
            valves = object.__getattribute__(self, "valves")

            @wraps(original)
            async def generate_quiz(*args, **kwargs):
                return await original(*args, **kwargs)

            doc = original.__doc__ or ""

            if valves.quiz_mode == "flashcard":
                doc = dedent("""
            Generate a flashcard quiz and display it to the user.

            Args:
                title (str):
                    The title of the quiz.

                questions (list[dict]):
                    A list of question objects. Each dictionary MUST contain
                    these two keys:
                        - "question" (str): The question text.
                        - "answer"   (str): The single CORRECT answer,
                                        written out in full.

                    Example of one valid item:
                        {
                            "question": "What is the capital of France?",
                            "answer": "Paris"
                        }

                    Write the answer only once, in "answer".
                    Do not rename any key.
                    Every item must follow this exact structure or the quiz
                    will fail to generate.

            Returns:
                Generated quiz accessible to the user,
                or an error message.
            """)
            if valves.enable_explanations:
                doc += dedent("""

            Additional requirement:
                Each question dict MUST also include an "explanation" (str) key —
                a concise explanation of why the correct answer is correct, written
                to teach the underlying concept.
            """)
            generate_quiz.__doc__ = doc
            return generate_quiz

        return object.__getattribute__(self, name)

    async def generate_quiz(self, title, questions: list[dict]):
        """
        Generate a multiple-choice quiz and display it to the user.

        Args:
            title (str):
                The title of the quiz.

            questions (list[dict]):
                A list of question objects. Each dictionary MUST contain
                these three keys:
                    - "question"    (str)       The question text.
                    - "answer"      (str)       The single CORRECT answer,
                                                 written out in full.
                    - "distractors" (list[str]) 1 or more WRONG answers.
                                                 Do not include the correct
                                                 answer in this list.

                Example of one valid item:
                    {
                        "question": "What is the capital of France?",
                        "answer": "Paris",
                        "distractors": ["Berlin", "Rome", "Madrid"]
                    }

                Write the answer only once, in "answer" — do not also
                repeat it inside "distractors". Do not rename any key.
                Every item must follow this exact structure or the quiz
                will fail to generate.

        Returns:
            Generated quiz accessible to the user,
            or an error message.
        """
        try:
            questions_and_answers, warnings = normalize_questions(
                questions, self.valves.quiz_mode
            )

            if not questions_and_answers:
                error_report = "\n".join(f"- {w}" for w in warnings)
                if self.valves.quiz_mode == "flashcards":
                    requirements = (
                        "Please regenerate the JSON. Each item needs 'question' "
                        "(string) and 'answer' (string, the correct answer)."
                    )
                else:
                    requirements = (
                        "Please regenerate the JSON. Each item needs 'question' "
                        "(string), 'answer' (string, the correct answer), and "
                        "'distractors' (a list of at least 1 wrong answer)."
                    )

                return (
                    "The quiz could not be generated because no valid "
                    "questions could be recovered from 'questions':\n\n"
                    f"{error_report}\n\n"
                    f"{requirements}"
                )

            choice_reference_patterns = [
                pattern.strip()
                for pattern in self.valves.choice_reference_patterns.split("|")
                if pattern.strip()
            ]

            if self.valves.shuffle_choices and self.valves.quiz_mode != "flashcards":
                shuffle_options(
                    questions_and_answers,
                    self.valves.prevent_reference_shuffle,
                    r"\p{L}",
                    choice_reference_patterns,
                )
            # Convert paragraphs and markdown tables to HTML per-question
            for q in questions_and_answers:
                q["question"] = _markdown_to_html(q.get("question", ""))
                q["options"] = [_markdown_to_html(opt) for opt in q.get("options", [])]
                if "explanation" in q:
                    q["explanation"] = _markdown_to_html(q["explanation"])

            quiz = {"title": title, "questions": questions_and_answers}

            # Modify Theme

            option_dark = self.valves.dark_theme
            option_light = self.valves.light_theme

            if self.valves.theme_mode == "light":
                option_dark = option_light
            elif self.valves.theme_mode == "dark":
                option_light = option_dark

            dark_theme = THEMES.get(option_dark, THEMES["default_dark"])
            light_theme = THEMES.get(option_light, THEMES["default_light"])

            # Generate quiz
            content = wrap_html(
                quiz,
                self.valves.enable_mathjax,
                light_theme,
                dark_theme,
                "mcq"
                if self.valves.quiz_mode == "multiple-choice questions"
                else "flashcard",
            )
            return HTMLResponse(
                content=content,
                headers={"Content-Disposition": "inline"},
            )

        except Exception as e:
            return f"An unexpected error occurred: {e}"


# =========================
# NORMALIZATION
# =========================

# Accepted synonyms for each field, since weaker models often use a
# slightly different key name than the one requested.
_QUESTION_KEYS = ("question", "q", "prompt", "text")
_ANSWER_KEYS = ("answer", "correct", "correct_answer", "correct_option")
_DISTRACTOR_KEYS = (
    "distractors",
    "wrong_answers",
    "incorrect_answers",
    "wrong_options",
)
_EXPLANATION_KEYS = ("explanation", "rationale", "why", "reason")


def _first_present(d: dict, keys, expected_type=None):
    for k in keys:
        if k in d:
            v = d[k]
            if expected_type is None or isinstance(v, expected_type):
                return v
    return None


def _markdown_to_html(text):
    code = []

    def protect(match):
        code.append(match.group(0))
        return f"\x00CODE{len(code) - 1}\x00"

    text = re.sub(r"`[^`]*`", protect, text)
    text = markdown.markdown(text, extensions=["tables"])

    for i, value in enumerate(code):
        text = text.replace(f"\x00CODE{i}\x00", value)

    return text


def normalize_questions(questions, mode) -> tuple[list[dict], list[str]]:
    """
    Best-effort cleanup of whatever the model produced.

    Returns (normalized_questions, warnings). Items that can't be
    salvaged are skipped (with a warning) rather than aborting the
    whole quiz — one bad question shouldn't sink the other nine.
    """
    warnings: list[str] = []

    if not isinstance(questions, list):
        return [], [
            (
                f"'questions' must be a list of question objects, got "
                f"'{type(questions).__name__}'."
            )
        ]

    normalized = []

    for i, q in enumerate(questions):
        label = f"Question at position {i}"

        if not isinstance(q, dict):
            warnings.append(f"{label} is not an object — skipped.")
            continue

        question_text = _first_present(q, _QUESTION_KEYS)

        if question_text is None:
            warnings.append(f"{label} is missing question text — skipped.")
            continue

        question_text = str(question_text)

        if not question_text.strip():
            warnings.append(f"{label} is missing question text — skipped.")
            continue

        options = None
        correct_index = None

        # --- Preferred path: answer + distractors -------------------
        # No text-matching needed here: we build the option list
        # ourselves, so the correct answer can't fail to line up with
        # itself the way it could when the model had to repeat it
        # verbatim inside an "options" array.
        answer_text = _first_present(q, _ANSWER_KEYS)

        if answer_text is not None:
            answer_text = str(answer_text)

        distractors = _first_present(q, _DISTRACTOR_KEYS, list)

        if answer_text:
            if mode == "flashcards":
                options = [answer_text]
                correct_index = 0

            elif distractors:
                distractors = [str(d) for d in distractors if str(d).strip()]

                # Guard against the model accidentally repeating the
                # answer inside distractors too (ignoring case/punctuation
                # so "Paris." doesn't slip past "Paris").
                norm_answer = answer_text.strip().lower().rstrip(".")
                distractors = [
                    d
                    for d in distractors
                    if d.strip().lower().rstrip(".") != norm_answer
                ]
                if distractors:
                    options = [answer_text] + distractors
                    correct_index = 0

        if options is None or correct_index is None:
            if mode == "flashcards":
                warnings.append(
                    f"{label} ('{question_text[:40]}...') — could not determine "
                    f"a valid answer — skipped."
                )
            else:
                warnings.append(
                    f"{label} ('{question_text[:40]}...') — could not determine "
                    f"a valid answer and distractors — skipped."
                )
            continue

        explanation = _first_present(q, _EXPLANATION_KEYS)
        if explanation is not None:
            explanation = str(explanation).strip() or None

        item = {
            "id": q.get("id") or f"q{i + 1}",
            "question": question_text,
            "options": options,
            "correct_index": correct_index,
        }
        if explanation:
            item["explanation"] = explanation

        normalized.append(item)

    return normalized, warnings


# =========================
# QUIZ LOGIC
# =========================


def shuffle_options(
    questions: list[dict],
    prevent_reference_shuffle: bool = False,
    choice_pattern: str = r"\p{L}",
    choice_reference_patterns: list[str] | None = None,
):

    if choice_reference_patterns is None:
        choice_reference_patterns = []

    for question in questions:
        choices = question["options"]

        if prevent_reference_shuffle and any(
            refers_to_other_options(
                choice,
                choice_pattern,
                choice_reference_patterns,
            )
            for choice in choices
        ):
            continue

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


def refers_to_other_options(
    text: str,
    choice_pattern: str,
    choice_reference_patterns: list[str],
) -> bool:
    choice = rf"(?:{choice_pattern})"

    choice_noun_en = (
        r"(?:answer|answers|option|options|choice|choices|"
        r"statement|statements)"
    )

    choice_noun_fr = (
        r"(?:réponse|réponses|option|options|choix|"
        r"affirmation|affirmations|proposition|propositions|"
        r"énoncé|énoncés)"
    )

    relative_en = (
        r"(?:above|previous|following|"
        r"listed\s+above|listed\s+previously)"
    )

    relative_fr = (
        r"(?:ci-dessus|ci-avant|précédent(?:e|s|es)?|"
        r"suivant(?:e|s|es)?)"
    )

    # A, B, C / A and B / A, B, and C
    choice_list_en = (
        rf"{choice}"
        rf"(?:\s*,\s*{choice})*"
        rf"(?:\s*,)?\s+and\s+{choice}"
    )

    choice_list_fr = (
        rf"{choice}"
        rf"(?:\s*,\s*{choice})*"
        rf"(?:\s*,)?\s+et\s+{choice}"
    )

    # A–C / A-C / A through C / A à C
    choice_range = rf"{choice}\s*(?:[-–]|through|à)\s*{choice}"

    patterns = [
        # True/False choices.
        r"^\s*(?:true|false)\s*$",
        r"^\s*(?:vrai|faux)\s*$",
        # Explicit references to a choice label.
        rf"\b{choice_noun_en}\s+{choice}\b",
        rf"\b{choice_noun_fr}\s+{choice}\b",
        # Explicit references to a choice by relative position.
        rf"\b(?:the\s+)?{choice_noun_en}\s+{relative_en}\b",
        rf"\b(?:the\s+)?{relative_en}\s+{choice_noun_en}\b",
        rf"\b(?:le|la|les)\s+{choice_noun_fr}\s+{relative_fr}\b",
        rf"\b(?:le|la|les)\s+{relative_fr}\s+{choice_noun_fr}\b",
        # Choice lists.
        rf"\b{choice_list_en}\b",
        rf"\b{choice_list_fr}\b",
        # Choice ranges.
        rf"\b{choice_range}\b",
        # A range/list preceded by a choice noun.
        rf"\b{choice_noun_en}\s+{choice_range}\b",
        rf"\b{choice_noun_fr}\s+{choice_range}\b",
        # "statements in A–C", "propositions de A à C".
        rf"\b{choice_noun_en}\s+(?:in|from)\s+{choice_range}\b",
        rf"\b{choice_noun_fr}\s+(?:de|parmi)\s+{choice_range}\b",
        # All/none of a referenced group.
        (
            r"\b(?:all|none)\s+of\s+the\s+"
            r"(?:above|following)\b"
        ),
        (
            r"\b(?:toutes?|aucune)\s+les?\s+"
            rf"{choice_noun_fr}\s+{relative_fr}\b"
        ),
        # "tout ce qui précède".
        r"\btout\s+ce\s+qui\s+précède\b",
        # Existing correctness forms.
        (
            rf"\b{choice_list_en}\s+"
            r"(?:are|is)\s+(?:all\s+)?"
            r"(?:correct|true|accurate|valid)\b"
        ),
        (
            rf"\b{choice_list_fr}\s+"
            r"(?:sont|est)\s+(?:toutes?\s+)?"
            r"(?:correctes?|vraies|exactes|justes|valides)\b"
        ),
        (
            rf"\b{choice_range}\s+"
            r"(?:are|is)\s+(?:all\s+)?"
            r"(?:correct|true|accurate|valid)\b"
        ),
        (
            rf"\b{choice_range}\s+"
            r"(?:sont|est)\s+(?:toutes?\s+)?"
            r"(?:correctes?|vraies|exactes|justes|valides)\b"
        ),
    ]

    patterns.extend(choice_reference_patterns)

    for pattern in patterns:
        if "previous" in pattern:
            print(repr(pattern))
            print(regex.search(pattern, text, regex.IGNORECASE))
    return any(regex.search(pattern, text, regex.IGNORECASE) for pattern in patterns)


# =========================
# HTML WRAPPER
# =========================


def wrap_html(
    quiz, enable_mathjax: bool, light_theme="default_light", dark_theme="default_dark", default_mode="mcq"
):

    import json

    payload = {"enableMathJax": bool(enable_mathjax), "mode": default_mode, "quiz": quiz}

    app_data = json.dumps(payload, ensure_ascii=False)

    return (
        HTML_TEMPLATE
        .replace("__APP_DATA__", app_data)
        .replace("__LIGHT_THEME__", light_theme)
        .replace("__DARK_THEME__", dark_theme)
    )


HTML_TEMPLATE = r"""<!doctype html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title id="page-title">Open-QuizUI</title>

    <link
      rel="icon"
      href="https://raw.githubusercontent.com/axel-chamberland/Open-QuizUI/main/frontend/assets/action_logo.svg"
    />

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

:is(:fullscreen, .pseudo-fullscreen-active) .page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

:is(:fullscreen, .pseudo-fullscreen-active) .navigation-scroll {
  flex: 0 0 auto;
  order: 1;
}

h1 {
  font-size: 1.2rem;
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

.page {
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

#question-scroll,
#flashcard-scroll {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:is(:fullscreen, .pseudo-fullscreen-active)
  :is(#question-scroll, #flashcard-scroll) {
  flex: 1;
  order: 0;
  overflow-y: auto;
}

#options {
  display: grid;
  max-width: 100%;
  gap: 0.75rem;
}

button {
  border: 1px solid;
  border-radius: 0.25rem;
  border-color: var(--border);
  background: var(--btn);
  cursor: pointer;
  color: var(--text);
  font-size: 1.1rem;

  display: inline-flex;
  align-items: center;
  justify-content: center;
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

.flashcard-answer {
  display: none;
}

.flashcard-answer.visible {
  display: block;

  margin-top: 1rem;
  padding: 5rem;

  border-top: 1px solid var(--border);

  background: var(--btn);
  border: 1px solid var(--border);
  border-radius: 0.5rem;

  text-align: center;
  font-size: 1.1rem;
}

.flashcard-question {
  padding: 5rem;
  margin: 0;

  background: var(--btn);
  border: 1px solid var(--border);
  border-radius: 0.5rem;

  text-align: center;
  font-size: 1.1rem;
}

.flashcard-explanation {
  margin-top: 1rem;
  padding: 0.75rem;

  background: var(--btn);

  border-radius: 0.5rem;
  font-size: 1em;
  opacity: 0.8;
}

#flashcard-rating {
  display: none;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}

.flashcard-rating-button {
  width: 3rem;
  height: 3rem;

  font-size: 1.5rem;
  line-height: 1;

  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--btn);
  color: var(--text);
  cursor: pointer;
}

.known-button {
  color: var(--success);
}

.unknown-button {
  color: var(--danger);
}
#explanation {
  display: none;
  margin-top: 1rem;
  padding: 0.75rem;
  background: var(--btn);
  border-radius: 0.5rem;
  opacity: 0.8;
}

.navigation-scroll {
  overflow-x: auto;
  overflow-y: hidden;
}

.navigation {
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

.navigation button {
  font-size: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

:is(:fullscreen, .pseudo-fullscreen-active) .navigation {
  margin: 0;
  border: 0;
  border-top: 1px solid var(--border);
}

.reveal-button,
.maximize-button,
.download-button,
.question-selector {
  flex: 0 0 auto;
  min-width: 2rem;
}

.prev-button,
.next-button {
  flex: 1;
  font-size: clamp(1.5rem, 5vw, 2rem);
  max-width: 4rem;
}

.question-selector {
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

.question-number {
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

.question-number:focus {
  outline: none;
  border: none;
}

.question-count {
  margin-right: 0.3em;
}

mjx-container {
  max-width: 100%;
  overflow-x: auto;
  white-space: normal;
}

/* Hide timer by default */
.timer {
  display: none;
  min-width: 4rem;
  font-size: 1.1rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.timer.visible {
  display: inline-block;
}

#correct,
.correct {
  color: var(--success);
}

#wrong,
.wrong {
  color: var(--danger);
}

#unanswered,
.unanswered {
  color: var(--unanswered);
}

#skipped,
.skipped {
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

#restart-confirm {
  display: none;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--btn);
}

#restart-confirm button {
  padding: 0.25rem 0.75rem;
}

#confirm-restart-button {
  color: var(--danger);
  border-color: var(--danger);
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

.stat-row > div {
  flex: 1;
  padding: 0.5rem;
  border-radius: 0.5rem;
  background: var(--btn);
}

#stats-chart {
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
  box-sizing: border-box;
}

textarea {
  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 1rem;
  field-sizing: content;
  width: 100%;
  max-width: 100%;
  resize: vertical;
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
  height: auto;
}

#editor-distractors .delete-prompt {
  display: none;
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
  font-size: 1rem;
  text-align: center;
}

.dropdown-menu {
  position: fixed;

  display: none;
  z-index: 2000;
  width: max-content;

  border: 1px solid var(--border);
  background: var(--bg);
}

.dropdown-menu button {
  display: grid;
  grid-template-columns: 1em 1fr;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  border: none;
  border-radius: 0;
  text-align: left;
  white-space: nowrap;
  padding: 0.5rem;
}

.dropdown-menu button svg {
  width: 1em;
  height: 1em;
}

.dropdown-menu.show {
  display: block;
}

.dropdown-menu button + button {
  border-top: 1px solid var(--border);
}

.global-prompt {
  display: none;
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 9999;

  padding: 1rem;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  width: fit-content;
  filter: drop-shadow(0 0 0.5rem var(--border));
}

.global-prompt.visible {
  display: block;
}

.global-prompt .button-row {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

/* image and embedded styles */
img,
video,
iframe {
  display: block;
  max-width: 100%;
  object-fit: contain;
  margin-inline: auto;
}

/* Tables */
table {
  max-width: 100%;
  margin: 1rem auto;
  border-collapse: collapse;
}

th,
td {
  padding: 0.5rem;
  border: 1px solid var(--border);
  text-align: left;
}

th {
  background: var(--btn);
}

</style>
  </head>

  <body class="app-loading">
    <svg style="display: none">
      <symbol id="icon-reveal" viewBox="0 0 24 24">
        <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z" />
        <circle cx="12" cy="12" r="2.5" />
      </symbol>
      <symbol id="icon-fullscreen" viewBox="0 0 24 24">
        <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
      </symbol>

      <symbol id="icon-download" viewBox="0 0 24 24">
        <path d="M12 3v12m0 0 5-5m-5 5-5-5M4 21h16" />
      </symbol>

      <symbol id="icon-timer" viewBox="0 0 24 24">
        <circle cx="12" cy="13" r="8" />
        <path d="M12 9v4l3 2M9 3h6" />
      </symbol>

      <symbol id="icon-editor" viewBox="0 0 24 24">
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 3h6v3H9z" />
        <path d="M8 11h8M8 15h5" />
      </symbol>
      <symbol
        id="icon-copy"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path
          d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
        ></path>
      </symbol>

      <symbol
        id="icon-copy-all"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
        <polyline points="2 17 12 22 22 17"></polyline>
        <polyline points="2 12 12 17 22 12"></polyline>
      </symbol>

      <symbol
        id="icon-save"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"
        ></path>
        <polyline points="17 21 17 13 7 13 7 21"></polyline>
        <polyline points="7 3 7 8 15 8"></polyline>
      </symbol>

      <symbol
        id="icon-close"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </symbol>

      <symbol
        id="icon-more"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="lucide lucide-ellipsis-vertical"
      >
        <circle cx="12" cy="12" r="1" />
        <circle cx="12" cy="5" r="1" />
        <circle cx="12" cy="19" r="1" />
      </symbol>
      <symbol
        id="switch-mode"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="lucide lucide-arrow-left-right preview-icon"
      >
        <path d="M8 3 4 7l4 4" />
        <path d="M4 7h16" />
        <path d="m16 21 4-4-4-4" />
        <path d="M20 17H4" />
      </symbol>
    </svg>
    <div id="global-prompt" class="global-prompt">
      <p id="global-prompt-message"></p>
      <div class="button-row">
        <button id="global-prompt-yes">yes</button>
        <button id="global-prompt-no">no</button>
      </div>
    </div>
    <div id="question-box" class="page" style="display: none">
      <div class="title-bar">
        <h1 class="title">Quiz</h1>
        <span class="timer">00:00</span>
      </div>
      <div class="navigation-scroll">
        <div class="navigation">
          <button class="prev-button" aria-label="Previous question">
            &lt;
          </button>

          <div class="question-selector">
            <input
              class="question-number"
              type="text"
              inputmode="numeric"
              value="1"
            />
            <span class="separator">/</span>
            <span class="question-count">1</span>
          </div>

          <button class="next-button" aria-label="Next question">&gt;</button>

          <button
            class="reveal-button"
            title="Reveal answer"
            aria-label="Reveal answer"
          >
            <svg><use href="#icon-reveal"></use></svg>
          </button>
          <button
            class="timer-toggle-button"
            title="Toggle timer"
            aria-label="Toggle timer"
          >
            <svg><use href="#icon-timer"></use></svg>
          </button>
          <button
            class="mode-button"
            title="Switch to Flashcards mode"
            aria-label="Switch to Flashcards mode"
          >
            <svg><use href="#switch-mode"></use></svg>
          </button>
          <button
            class="maximize-button"
            title="Toggle Fullscreen"
            aria-label="Fullscreen"
          >
            <svg><use href="#icon-fullscreen"></use></svg>
          </button>
          <button
            class="copy-question-button"
            title="Copy question"
            aria-label="Copy question"
          >
            <svg><use href="#icon-copy"></use></svg>
          </button>
          <button class="dropdown-trigger" id="mcq-menu-button">
            <svg><use href="#icon-more"></use></svg>
          </button>
        </div>
      </div>
      <div class="dropdown-menu" id="mcq-dropdown-menu">
        <button
          class="editor-button"
          title="Edit question"
          aria-label="Edit question"
        >
          <svg><use href="#icon-editor"></use></svg>
          Edit question
        </button>
        <button
          class="download-button"
          title="Download quiz"
          aria-label="Download quiz"
        >
          <svg><use href="#icon-download"></use></svg>
          Download
        </button>
        <button
          class="copy-all-button"
          title="Copy quiz"
          aria-label="Copy quiz"
        >
          <svg><use href="#icon-copy-all"></use></svg>Copy Quiz
        </button>
      </div>
      <div id="question-scroll">
        <p id="question"></p>
        <div id="options"></div>
        <div id="explanation"></div>
      </div>
    </div>

    <div id="flashcard-box" class="page" style="display: none">
      <div class="title-bar">
        <h1 class="title">Flashcards</h1>
        <span class="timer">00:00</span>
      </div>

      <div class="navigation-scroll">
        <div class="navigation">
          <button class="prev-button" aria-label="Previous question">
            &lt;
          </button>

          <div class="question-selector">
            <input
              class="question-number"
              type="text"
              inputmode="numeric"
              value="1"
            />
            <span class="separator">/</span>
            <span class="question-count">1</span>
          </div>

          <button class="next-button" aria-label="Next question">&gt;</button>

          <button
            class="reveal-button"
            title="Reveal answer"
            aria-label="Reveal answer"
          >
            <svg><use href="#icon-reveal"></use></svg>
          </button>

          <button
            class="timer-toggle-button"
            title="Toggle timer"
            aria-label="Toggle timer"
          >
            <svg><use href="#icon-timer"></use></svg>
          </button>
          <button
            class="mode-button"
            title="Switch to MCQ mode"
            aria-label="Switch to MCQ mode"
          >
            <svg><use href="#switch-mode"></use></svg>
          </button>
          <button
            class="maximize-button"
            title="Toggle Fullscreen"
            aria-label="Fullscreen"
          >
            <svg><use href="#icon-fullscreen"></use></svg>
          </button>
          <button
            class="copy-question-button"
            title="Copy question"
            aria-label="Copy question"
          >
            <svg><use href="#icon-copy"></use></svg>
          </button>
          <button class="dropdown-trigger" id="flashcard-menu-button">
            <svg><use href="#icon-more"></use></svg>
          </button>
        </div>
      </div>
      <div class="dropdown-menu" id="flashcard-dropdown-menu">
        <button
          class="editor-button"
          title="Edit question"
          aria-label="Edit question"
        >
          <svg><use href="#icon-editor"></use></svg>
          Edit question
        </button>
        <button
          class="download-button"
          title="Download flashcards"
          aria-label="Download quiz"
        >
          <svg><use href="#icon-download"></use></svg>
          Download
        </button>
        <button
          class="copy-all-button"
          title="Copy flashcards"
          aria-label="Copy flashcards"
        >
          <svg><use href="#icon-copy-all"></use></svg>Copy Quiz
        </button>
      </div>

      <div id="flashcard-scroll">
        <p class="flashcard-question"></p>
        <div class="flashcard-answer"></div>
        <div class="flashcard-explanation"></div>
      </div>

      <div id="flashcard-rating" class="button-row">
        <button class="flashcard-rating-button unknown-button">✗</button>
        <button class="flashcard-rating-button known-button">✓</button>
      </div>
    </div>

    <div id="results" class="page" style="display: none">
      <div class="navigation-scroll">
        <div id="results-navigation" class="navigation">
          <button
            id="results-back-button"
            title="Back to quiz"
            aria-label="Back to quiz"
          >
            &lt;
          </button>

          <button
            class="maximize-button"
            title="Toggle Fullscreen"
            aria-label="Fullscreen"
          >
            <svg><use href="#icon-fullscreen"></use></svg>
          </button>

          <button
            class="download-button"
            title="Download quiz"
            aria-label="Download quiz"
          >
            <svg><use href="#icon-download"></use></svg>
          </button>

          <button
            class="copy-all-button"
            title="Copy quiz"
            aria-label="Copy quiz"
          >
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

        <div id="stats-chart"></div>

        <button id="restart-button" aria-label="Restart quiz">
          Restart Quiz
        </button>

        <div id="restart-confirm">
          <span>Restart quiz? <i>Your results will be reset.</i></span>
          <button id="confirm-restart-button" aria-label="Confirm restart">
            Yes
          </button>
          <button id="cancel-restart-button" aria-label="Cancel restart">
            No
          </button>
        </div>

        <section class="correction-sheet">
          <h2>Correction</h2>
          <div id="question-corrections"></div>
        </section>
      </div>
    </div>

    <div id="editor" class="page" style="display: none">
      <h1>Question Editor</h1>
      <div class="navigation-scroll">
        <div id="editor-navigation" class="navigation">
          <button
            id="editor-save-button"
            title="Save changes"
            aria-label="Save changes"
            data-tooltip="Save changes"
          >
            <svg><use href="#icon-save"></use></svg>
          </button>
          <button
            class="copy-all-button"
            title="Copy quiz"
            aria-label="Copy quiz"
          >
            <svg><use href="#icon-copy-all"></use></svg>
          </button>
          <button
            class="copy-question-button"
            title="Copy question"
            aria-label="Copy question"
          >
            <svg><use href="#icon-copy"></use></svg>
          </button>
          <button
            class="maximize-button"
            title="Fullscreen"
            aria-label="Fullscreen"
          >
            <svg><use href="#icon-fullscreen"></use></svg>
          </button>
          <button class="dropdown-trigger" id="editor-menu-button">
            <svg><use href="#icon-more"></use></svg>
          </button>
          <button
            id="editor-close-button"
            title="Close editor"
            aria-label="Close editor"
            data-tooltip="Close editor"
          >
            <svg><use href="#icon-close"></use></svg>
          </button>
        </div>
      </div>
      <div class="dropdown-menu" id="editor-dropdown-menu">
        <button
          id="reset-quiz-button"
          title="Reset all questions"
          aria-label="Reset quiz"
          data-tooltip="Reset quiz"
        >
          Reset Quiz
        </button>
        <button
          id="reset-question-button"
          title="Reset current question"
          aria-label="Reset question"
          data-tooltip="Reset question"
        >
          Reset Question
        </button>
      </div>
      <p>
        <strong>Limitation:</strong>
        Changes are stored in your browser.<br />
        Download the modified quiz as a new HTML file to keep your changes
        permanently.
      </p>
      <div id="editor-scroll">
        <p><strong>Title:</strong></p>
        <div id="editor-title"></div>
        <p><strong>Question:</strong></p>
        <div id="editor-question"></div>
        <div class="answer-position">
          <p><strong>Answer Position:</strong></p>
          <input type="text" id="editor-answer-number" inputmode="numeric" />
        </div>
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
    const index = Number(localStorage.getItem(getProgressKey(quizStorageKey)));
    if (!Number.isInteger(index)) {
      return 0;
    }
    return Math.max(0, Math.min(index, state.quiz.questions.length));
  } catch {
    return 0;
  }
}
function setStoredQuestionIndex(quizStorageKey, value) {
  try {
    localStorage.setItem(getProgressKey(quizStorageKey), String(value));
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
  mode: null,
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
  function protect(value) {
    const index = protectedParts.length;
    protectedParts.push(value);
    return `\uE000${index}\uE001`;
  }
  text = text.replace(
    /```(?:[^\n`]*)\n([\s\S]*?)```/g,
    (_, content) => protect(`<pre><code>${escapeHtml(content)}</code></pre>`)
  );
  text = text.replace(
    /`([^`]*?)`/g,
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
function toMarkdown(text) {
  if (!text) return "";
  text = renderMarkdown(text, true);
  const container = document.createElement("div");
  container.innerHTML = text;
  function convert(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    const tag = node.tagName.toLowerCase();
    const content = [...node.childNodes].map(convert).join("");
    switch (tag) {
      // Text formatting
      case "strong":
      case "b":
        return `**${content}**`;
      case "em":
      case "i":
        return `*${content}*`;
      case "u":
        return `<u>${content}</u>`;
      case "s":
      case "strike":
      case "del":
        return `~~${content}~~`;
      // Paragraphs
      case "p":
        return `${content}

`;
      case "br":
        return "\n";
      case "hr":
        return "\n\n---\n\n";
      // Links
      case "a": {
        const href = node.getAttribute("href");
        if (!href && !content.trim()) {
          return "<a>";
        }
        if (!href) {
          return content;
        }
        const title = node.getAttribute("title");
        const titlePart = title ? ` "${title}"` : "";
        return `[${content}](${href}${titlePart})`;
      }
      // Images
      case "img": {
        const src = node.getAttribute("src");
        if (!src) {
          return "<img>";
        }
        const alt = node.getAttribute("alt") || "";
        const title = node.getAttribute("title");
        const titlePart = title ? ` "${title}"` : "";
        return `![${alt}](${src}${titlePart})`;
      }
      // Code
      case "code":
        if (node.parentElement?.tagName.toLowerCase() === "pre") {
          return content;
        }
        return `\`${content.replace(/`/g, "\\`")}\``;
      case "pre": {
        const code = node.querySelector(":scope > code");
        const value = code ? code.textContent : node.textContent;
        return `

\`\`\`
${value.replace(/\n+$/, "")}
\`\`\`

`;
      }
      // Lists
      case "ul":
        return "\n\n" + [...node.children].filter(
          (child) => child.tagName.toLowerCase() === "li"
        ).map((child) => `- ${convert(child).trim()}`).join("\n") + "\n\n";
      case "ol":
        return "\n\n" + [...node.children].filter(
          (child) => child.tagName.toLowerCase() === "li"
        ).map(
          (child, index) => `${index + 1}. ${convert(child).trim()}`
        ).join("\n") + "\n\n";
      case "li":
        return content;
      // Tables
      case "table":
        return convertTable(node);
      // Blockquote
      case "blockquote":
        return "\n\n" + content.trim().split("\n").map((line) => `> ${line}`).join("\n") + "\n\n";
      // Headings
      case "h1":
      case "h2":
      case "h3":
      case "h4":
      case "h5":
      case "h6": {
        const level = Number(tag[1]);
        return `

${"#".repeat(level)} ${content.trim()}

`;
      }
      // Media with no Markdown equivalent
      case "video":
      case "audio":
      case "iframe":
        return node.outerHTML;
      // Other elements: preserve their contents
      default:
        return content;
    }
  }
  function convertTable(table) {
    const rows = [...table.querySelectorAll(":scope > tbody > tr, :scope > tr")];
    if (!rows.length) {
      return "";
    }
    const data = rows.map(
      (row) => [...row.children].filter(
        (cell) => ["th", "td"].includes(cell.tagName.toLowerCase())
      ).map(
        (cell) => convert(cell).trim().replace(/\|/g, "\\|").replace(/\n+/g, " ")
      )
    );
    if (!data.length) {
      return "";
    }
    const columnCount = Math.max(...data.map((row) => row.length));
    const header = Array.from(
      { length: columnCount },
      (_, i) => data[0][i] || ""
    );
    const separator = Array.from(
      { length: columnCount },
      () => "---"
    );
    const body = data.slice(1).map(
      (row) => Array.from(
        { length: columnCount },
        (_, i) => row[i] || ""
      )
    );
    return [
      "",
      `| ${header.join(" | ")} |`,
      `| ${separator.join(" | ")} |`,
      ...body.map((row) => `| ${row.join(" | ")} |`),
      ""
    ].join("\n");
  }
  return [...container.childNodes].map(convert).join("").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
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
async function typesetMath() {
  if (state.mathReady && window.MathJax) {
    try {
      await window.MathJax.typesetPromise();
    } catch (err) {
      console.error("MathJax typesetting failed:", err);
    }
  }
}

// frontend/src/rendering/mcq.js
function showMcqExplanation(question) {
  const explanationEl = document.getElementById("explanation");
  if (question.explanation) {
    explanationEl.innerHTML = renderMarkdown(
      question.explanation,
      state.mathReady
    );
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
async function renderMCQ() {
  const questionBox = document.getElementById("question-box");
  const questionText = questionBox.querySelector("#question");
  const optionsContainer = document.getElementById("options");
  const navigationContainer = questionBox.querySelector("#navigation");
  const explanationEl = document.getElementById("explanation");
  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    document.getElementById("question").textContent = "No valid questions parsed";
    return;
  }
  const question = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion = question;
  renderQuestion(questionText, question);
  explanationEl.textContent = "";
  explanationEl.style.display = "none";
  renderOptions(optionsContainer, question);
  updateNavigation();
  document.getElementById("question-scroll").scrollTop = 0;
  await typesetMath();
}
function renderOptions(optionsContainer, question) {
  optionsContainer.innerHTML = "";
  state.wrongAnswerCount = 0;
  state.optionButtons = [];
  question.options.forEach((option, index) => {
    const button = document.createElement("button");
    button.innerHTML = renderMarkdown(option, state.mathReady);
    button.className = "option";
    state.optionButtons.push(button);
    button.addEventListener("click", () => {
      handleAnswer(index, button);
    });
    optionsContainer.appendChild(button);
  });
}

// frontend/src/persistence/stats.js
function getStatsKey(quizStorageKey) {
  return `quizStats_${quizStorageKey}`;
}
function loadStats() {
  try {
    const data = JSON.parse(
      localStorage.getItem(getStatsKey(state.quizStorageKey))
    );
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
    state.questionResults = new Array(state.quiz.questions.length).fill(
      UNANSWERED
    );
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
  const questionText = toMarkdown(
    question.question
  );
  lines.push(`Question ${index + 1}: ${questionText}`);
  lines.push("");
  for (const [i, option] of question.options.entries()) {
    const letter = String.fromCharCode(65 + i);
    lines.push(
      `${letter}. ${toMarkdown(option)}`
    );
  }
  return lines.join("\n");
}
function formatAnswerKey(questions) {
  const lines = [
    "Answer Key:",
    "",
    "| Question | Correct Answer | Explanation |",
    "| --- | --- | --- |"
  ];
  const escapeTableCell = (text) => String(text ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
  for (const [index, question] of questions.entries()) {
    const correctLetter = String.fromCharCode(
      65 + question.correct_index
    );
    const explanation = toMarkdown(
      question.explanation || ""
    );
    lines.push(
      `| ${index + 1} | ${correctLetter} | ${escapeTableCell(explanation)} |`
    );
  }
  return lines.join("\n");
}
function formatQuizAsText(quiz2) {
  const lines = [
    toMarkdown(quiz2.title),
    ""
  ];
  for (const [index, question] of quiz2.questions.entries()) {
    lines.push(
      formatQuestionAsText(
        question,
        index
      )
    );
    lines.push("");
  }
  lines.push(
    formatAnswerKey(
      quiz2.questions
    )
  );
  return lines.join("\n").trim();
}

// frontend/src/timer.js
var timerElements = document.querySelectorAll(".timer");
function getTimerKey(quizStorageKey) {
  return `quizTimer_${quizStorageKey}`;
}
function loadTimer(state2) {
  try {
    const data = JSON.parse(
      localStorage.getItem(getTimerKey(state2.quizStorageKey))
    );
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
  timerElements.forEach((timerElement) => {
    timerElement.textContent = formatTime(elapsed);
  });
}
function toggleTimer() {
  state.timer.visible = !state.timer.visible;
  timerElements.forEach((timerElement) => {
    timerElement.classList.toggle("visible", state.timer.visible);
  });
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
      state.timer.elapsed += Math.floor(
        (Date.now() - state.timer.start) / 1e3
      );
      state.timer.start = null;
      saveTimer();
    }
    clearInterval(state.timer.interval);
    state.timer.interval = null;
  }
}

// frontend/src/rendering/flashcards.js
async function renderFlashcard() {
  const flashcardBox = document.getElementById("flashcard-box");
  const questionText = flashcardBox.querySelector(".flashcard-question");
  const answerEl = flashcardBox.querySelector(".flashcard-answer");
  const explanationEl = flashcardBox.querySelector(".flashcard-explanation");
  const ratingEl = flashcardBox.querySelector("#flashcard-rating");
  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    questionText.textContent = "No valid questions parsed";
    return;
  }
  answerEl.classList.remove("visible");
  explanationEl.style.display = "none";
  ratingEl.style.display = "none";
  const question = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion = question;
  renderQuestion(questionText, question);
  const answerIndex = question.options.length === 1 ? 0 : question.correct_index;
  answerEl.innerHTML = renderMarkdown(
    question.options[answerIndex],
    state.mathReady
  );
  state.answerRevealed = false;
  updateNavigation();
  flashcardBox.querySelector("#flashcard-scroll").scrollTop = 0;
  await typesetMath();
}
function showFlashcardExplanation(question) {
  const explanationEl = document.querySelector(".flashcard-explanation");
  if (question.explanation) {
    explanationEl.innerHTML = renderMarkdown(
      question.explanation,
      state.mathReady
    );
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
function rateFlashcard(correct) {
  if (!state.answerRevealed) {
    return;
  }
  state.questionResults[state.currentQuestionIndex] = correct ? CORRECT : WRONG;
  saveStats();
  nextQuestion();
}

// frontend/src/rendering/results.js
async function renderResults() {
  const results2 = document.getElementById("results");
  const flashcardBox = document.getElementById("flashcard-box");
  flashcardBox.style.display = "none";
  const questionBox = document.getElementById("question-box");
  questionBox.style.display = "none";
  results2.style.display = "";
  const correct = state.questionResults.filter((x) => x === CORRECT).length;
  const wrong = state.questionResults.filter((x) => x === WRONG).length;
  const unanswered = state.questionResults.filter(
    (x) => x === UNANSWERED
  ).length;
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
  createDonutChart(document.getElementById("stats-chart"), chartData);
  showCorrectionSheet();
  await typesetMath();
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
  const resultClass = {
    [CORRECT]: "correct",
    [WRONG]: "wrong",
    [UNANSWERED]: "unanswered",
    [SKIPPED]: "skipped"
  };
  for (let index = 0; index < questions.length; index++) {
    const question = questions[index];
    const correctAnswer = question.options[question.correct_index];
    const userIndex = state.questionAnswers[index];
    const userAnswer = state.mode === "flashcard" ? state.questionResults[index] === CORRECT ? "\u2713" : state.questionResults[index] === WRONG ? "\u2717" : "Unanswered" : state.questionResults[index] === SKIPPED ? "Skipped" : userIndex !== null ? question.options[userIndex] : "Unanswered";
    const article = document.createElement("article");
    const currentClass = resultClass[state.questionResults[index]];
    article.innerHTML = `

<h3 class="${currentClass}">Question ${index + 1}</h3>

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
  updateQuestionNumbers();
  state.answerRevealed = false;
  state.wrongAnswerCount = 0;
  state.questionResults = new Array(state.quiz.questions.length).fill(
    UNANSWERED
  );
  state.questionAnswers = new Array(state.quiz.questions.length).fill(null);
  document.getElementById("question-corrections").innerHTML = "";
  clearInterval(state.timer.interval);
  state.timer.interval = null;
  state.timer.elapsed = 0;
  state.timer.start = state.timer.visible ? Date.now() : null;
  state.defaultStartDate = Date.now();
  const timerElements2 = document.querySelectorAll(".timer");
  if (state.timer.visible) {
    updateTimer();
    state.timer.interval = setInterval(updateTimer, 1e3);
  } else {
    timerElements2.forEach((timerElement) => {
      timerElement.textContent = formatTime(0);
    });
  }
  saveTimer();
  setStoredQuestionIndex(state.quizStorageKey, 0);
  const results2 = document.getElementById("results");
  results2.style.display = "none";
  document.getElementById("restart-confirm").style.display = "none";
  if (state.mode === "flashcard") {
    const flashcardBox = document.getElementById("flashcard-box");
    flashcardBox.style.display = "";
    renderFlashcard();
    return;
  }
  const questionBox = document.getElementById("question-box");
  questionBox.style.display = "";
  document.getElementById("restart-confirm").style.display = "none";
  renderMCQ();
}
function confirmRestart() {
  document.getElementById("restart-confirm").style.display = "flex";
}
function cancelRestart() {
  document.getElementById("restart-confirm").style.display = "none";
}

// frontend/src/quiz.js
var results = document.getElementById("results");
function nextQuestion() {
  goTo(state.currentQuestionIndex + 1);
}
function prevQuestion() {
  if (state.currentQuestionIndex <= 0) return;
  const results2 = document.getElementById("results");
  results2.style.display = "none";
  goTo(state.currentQuestionIndex - 1);
}
function goTo(questionIndex) {
  const questionCount = state.quiz.questions.length;
  if (questionIndex < 0) {
    questionIndex = 0;
  }
  if (questionIndex >= questionCount) {
    state.currentQuestionIndex = questionCount;
    setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
    renderResults();
    return;
  }
  state.currentQuestionIndex = questionIndex;
  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
  state.answerRevealed = false;
  updateQuestionNumbers();
  const question = state.quiz.questions[questionIndex];
  const distractorCount = question.options.length - 1;
  let mode2 = state.mode;
  if (mode2 === "flashcard" || distractorCount < 2) {
    mode2 = "flashcard";
  }
  const quizPage = document.getElementById("question-box");
  const flashcardPage = document.getElementById("flashcard-box");
  if (mode2 === "flashcard") {
    quizPage.style.display = "none";
    flashcardPage.style.display = "";
    renderFlashcard();
    return;
  }
  quizPage.style.display = "";
  flashcardPage.style.display = "none";
  renderMCQ();
}
function updateQuestionNumbers() {
  document.querySelectorAll(".question-number").forEach((element) => {
    element.value = state.currentQuestionIndex + 1;
  });
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
    showMcqExplanation(state.currentQuestion);
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
  if (document.getElementById("flashcard-box").style.display !== "none") {
    document.querySelector(".flashcard-answer").classList.add("visible");
    showFlashcardExplanation(state.currentQuestion);
    document.getElementById("flashcard-rating").style.display = "flex";
    return;
  }
  state.currentQuestion = state.quiz.questions[state.currentQuestionIndex];
  const optionsContainer = document.getElementById("options");
  const buttons = optionsContainer.querySelectorAll("button");
  buttons[state.currentQuestion.correct_index].classList.add("correct");
  showMcqExplanation(state.currentQuestion);
}
function setQuizTitle(title) {
  const displayTitle = title.slice(0, 60);
  document.title = displayTitle;
  document.querySelectorAll(".title").forEach((e) => e.textContent = title);
}
function renderQuestion(questionText, question) {
  questionText.innerHTML = renderMarkdown(question.question, state.mathReady);
}
function updateNavigation() {
  document.querySelectorAll(".prev-button").forEach((button) => {
    button.disabled = state.currentQuestionIndex === 0;
  });
}
function updateQuestionCounts() {
  document.querySelectorAll(".question-count").forEach((element) => {
    element.textContent = state.quiz.questions.length;
  });
}
function setMode(mode2) {
  state.mode = mode2;
  const quizPage = document.getElementById("question-box");
  const flashcardPage = document.getElementById("flashcard-box");
  const isFlashcard = mode2 === "flashcard";
  quizPage.style.display = isFlashcard ? "none" : "";
  flashcardPage.style.display = isFlashcard ? "" : "none";
}
function switchMode() {
  state.mode = state.mode === "mcq" ? "flashcard" : "mcq";
  setMode(state.mode);
  if (state.mode === "mcq") {
    renderMCQ();
  } else {
    renderFlashcard();
  }
}

// frontend/src/shared/download.js
function downloadQuizHTML() {
  const appData2 = {
    mode: state.mode,
    enableMathJax: state.mathReady,
    quiz: state.quiz
  };
  const filename = state.quiz.title;
  const documentClone = document.documentElement.cloneNode(true);
  const questionScroll = documentClone.querySelector("#question-scroll");
  if (questionScroll) {
    questionScroll.querySelector("#question")?.replaceChildren();
    questionScroll.querySelector("#options")?.replaceChildren();
    questionScroll.querySelector("#explanation")?.replaceChildren();
  }
  const flashcardBox = documentClone.querySelector("#flashcard-box");
  if (flashcardBox) {
    flashcardBox.querySelector(".flashcard-question")?.replaceChildren();
    flashcardBox.querySelector(".flashcard-answer")?.replaceChildren();
    flashcardBox.querySelector(".flashcard-explanation")?.replaceChildren();
  }
  documentClone.querySelectorAll(".dropdown-menu").forEach((menu) => {
    menu.classList.remove("show");
    menu.style.removeProperty("left");
    menu.style.removeProperty("top");
    menu.style.removeProperty("bottom");
  });
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
async function copyQuestion() {
  const question = state.quiz.questions[state.currentQuestionIndex];
  const quiz2 = {
    title: state.quiz.title,
    questions: [question]
  };
  await copyToClipboard(
    formatQuizAsText(
      quiz2
    )
  );
}
async function copyQuiz() {
  await copyToClipboard(
    formatQuizAsText(
      state.quiz
    )
  );
}
async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.error("Failed to copy:", error);
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
  const questionChanged = hasQuestionChanged(index);
  const actualTitleChanged = titleChanged && hasTitleChanged();
  if (!questionChanged && !actualTitleChanged) {
    return false;
  }
  if (actualTitleChanged) {
    edits.title = state.quiz.title;
  }
  if (questionChanged) {
    edits[index] = state.quiz.questions[index];
  }
  try {
    localStorage.setItem(key, JSON.stringify(edits));
    return true;
  } catch (e) {
    console.error("Failed to save edit:", e);
    return false;
  }
}
function hasQuestionChanged(index) {
  const appData2 = JSON.parse(document.getElementById("app-data").textContent);
  return JSON.stringify(state.quiz.questions[index]) !== JSON.stringify(appData2.quiz.questions[index]);
}
function hasTitleChanged() {
  const appData2 = JSON.parse(document.getElementById("app-data").textContent);
  return state.quiz.title !== appData2.quiz.title;
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
function removeLocalEdit(index) {
  const key = getQuizEditsKey(state.quizStorageKey);
  let edits;
  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return false;
  }
  delete edits[index];
  if (Object.keys(edits).length === 0) {
    localStorage.removeItem(key);
  } else {
    localStorage.setItem(key, JSON.stringify(edits));
  }
  return true;
}
function removeAllLocalEdits() {
  const key = getQuizEditsKey(state.quizStorageKey);
  localStorage.removeItem(key);
}

// frontend/src/ui/alert.js
function showPrompt(message, onYes = null, onNo = null, yesText = "yes", noText = "no") {
  const prompt = document.getElementById("global-prompt");
  const messageElement = document.getElementById("global-prompt-message");
  const yesButton = document.getElementById("global-prompt-yes");
  const noButton = document.getElementById("global-prompt-no");
  messageElement.textContent = message;
  yesButton.textContent = yesText;
  noButton.textContent = noText;
  yesButton.style.display = "";
  noButton.style.display = "";
  const close = (callback) => {
    prompt.classList.remove("visible");
    document.removeEventListener("keydown", keyHandler, true);
    if (callback) callback();
  };
  yesButton.onclick = () => close(onYes);
  noButton.onclick = () => close(onNo);
  function keyHandler(e) {
    if (e.key === "Enter" || e.key.toLowerCase() === "y") {
      e.preventDefault();
      e.stopPropagation();
      close(onYes);
    } else if (e.key.toLowerCase() === "n" || e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close(onNo);
    }
  }
  document.addEventListener("keydown", keyHandler, true);
  prompt.classList.add("visible");
}
function showAlert(message) {
  const prompt = document.getElementById("global-prompt");
  const messageElement = document.getElementById("global-prompt-message");
  const yesButton = document.getElementById("global-prompt-yes");
  const noButton = document.getElementById("global-prompt-no");
  messageElement.textContent = message;
  yesButton.textContent = "OK";
  yesButton.style.display = "";
  noButton.style.display = "none";
  const close = () => {
    prompt.classList.remove("visible");
    document.removeEventListener("keydown", keyHandler, true);
  };
  yesButton.onclick = close;
  function keyHandler(e) {
    if (e.key === "Enter" || e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
    }
  }
  document.addEventListener("keydown", keyHandler, true);
  prompt.classList.add("visible");
}

// frontend/src/rendering/editor.js
document.getElementById("editor-answer-number").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/\D/g, "");
});
function openEditor() {
  const editor = document.getElementById("editor");
  if (state.mode === "flashcard") {
    const flashcardBox = document.getElementById("flashcard-box");
    flashcardBox.style.display = "none";
  } else {
    const questionBox = document.getElementById("question-box");
    questionBox.style.display = "none";
  }
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
function validateAnswerIndex() {
  const answerInput = document.querySelector("#editor-answer-number");
  const val = parseInt(answerInput.value) - 1;
  const optionsContainer = document.getElementById("editor-distractors");
  const options = optionsContainer.querySelectorAll("article");
  if (val < 0 || val >= options.length) {
    answerInput.classList.add("input-error");
    showAlert("Invalid Index: The selected option no longer exists.");
    return false;
  }
  return true;
}
function closeEditorConfirm() {
  showPrompt(
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
    showAlert("Changes saved.");
  }
}
function closeEditor() {
  const editor = document.getElementById("editor");
  editor.style.display = "none";
  const options = document.getElementById("editor-distractors");
  options.innerHTML = "";
  if (state.mode === "flashcard") {
    const flashcardBox = document.getElementById("flashcard-box");
    flashcardBox.style.display = "";
  } else {
    const questionBox = document.getElementById("question-box");
    questionBox.style.display = "";
  }
  renderMCQ();
}
function restoreQuizToDefault() {
  showPrompt(
    "Restore the quiz to its original state?\nAll local edits will be discarded.",
    () => {
      const appData2 = JSON.parse(
        document.getElementById("app-data").textContent
      );
      state.quiz = structuredClone(appData2.quiz);
      setQuizTitle(state.quiz.title);
      removeAllLocalEdits();
      openEditor();
      showAlert("Quiz restored to default.");
    },
    null,
    "Yes",
    "No"
  );
}
function restoreQuestionToDefault() {
  showPrompt(
    "Restore the current question to its original state?\nAll local edits will be discarded.",
    () => {
      const appData2 = JSON.parse(
        document.getElementById("app-data").textContent
      );
      const index = state.currentQuestionIndex;
      state.quiz.questions[index] = structuredClone(
        appData2.quiz.questions[index]
      );
      removeLocalEdit(index);
      openEditor();
      showAlert("Question restored to default.");
    },
    null,
    "Yes",
    "No"
  );
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
  document.querySelectorAll(".reveal-button").forEach((button) => {
    button.addEventListener("click", revealAnswer);
  });
  document.querySelectorAll(".timer-toggle-button").forEach((button) => {
    button.addEventListener("click", toggleTimer);
  });
  document.querySelectorAll(".prev-button").forEach((button) => {
    button.addEventListener("click", prevQuestion);
  });
  document.querySelectorAll(".next-button").forEach((button) => {
    button.addEventListener("click", nextQuestion);
  });
  document.querySelectorAll(".download-button").forEach((button) => {
    button.addEventListener("click", downloadQuizHTML);
  });
  document.querySelectorAll(".maximize-button").forEach((button) => {
    button.addEventListener("click", toggleFullscreen);
  });
  document.querySelectorAll(".copy-all-button").forEach((button) => {
    button.addEventListener("click", copyQuiz);
  });
  document.querySelectorAll(".copy-question-button").forEach((button) => {
    button.addEventListener("click", copyQuestion);
  });
  document.querySelectorAll(".editor-button").forEach((button) => {
    button.addEventListener("click", openEditor);
  });
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", switchMode);
  });
  document.querySelector(".known-button").addEventListener("click", () => rateFlashcard(true));
  document.querySelector(".unknown-button").addEventListener("click", () => rateFlashcard(false));
  document.getElementById("results-back-button").addEventListener("click", prevQuestion);
  document.getElementById("restart-button").addEventListener("click", confirmRestart);
  document.getElementById("confirm-restart-button").addEventListener("click", restartQuiz);
  document.getElementById("cancel-restart-button").addEventListener("click", cancelRestart);
  document.getElementById("editor-save-button").addEventListener("click", saveEdit);
  document.getElementById("editor-close-button").addEventListener("click", closeEditorConfirm);
  document.getElementById("reset-quiz-button").addEventListener("click", restoreQuizToDefault);
  document.getElementById("reset-question-button").addEventListener("click", restoreQuestionToDefault);
  document.querySelectorAll(".dropdown-trigger").forEach((trigger) => {
    const menuId = trigger.id.replace("-menu-button", "-dropdown-menu");
    const menu = document.getElementById(menuId);
    const navigation = trigger.closest(".navigation");
    const navigationScroll = navigation.parentElement;
    const positionMenu = () => {
      if (!menu.classList.contains("show")) return;
      const rect = trigger.getBoundingClientRect();
      const navRect = navigationScroll.getBoundingClientRect();
      menu.style.left = `${Math.min(
        rect.right,
        navRect.right - menu.offsetWidth
      )}px`;
      if (document.fullscreenElement || document.documentElement.classList.contains("pseudo-fullscreen-active")) {
        menu.style.top = "auto";
        menu.style.bottom = `${document.documentElement.clientHeight - navRect.top}px`;
      } else {
        menu.style.top = `${rect.bottom}px`;
        menu.style.bottom = "auto";
      }
    };
    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("show");
      positionMenu();
    });
    const observer = new ResizeObserver(positionMenu);
    observer.observe(navigation);
    window.addEventListener("scroll", positionMenu, true);
    menu.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        menu.classList.remove("show");
      });
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".dropdown-trigger, .dropdown-menu")) {
        document.querySelectorAll(".dropdown-menu.show").forEach((menu2) => {
          menu2.classList.remove("show");
        });
      }
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (document.getElementById("question-box")?.style.display === "none" && document.getElementById("flashcard-box")?.style.display === "none") {
      return;
    }
    const key = e.key.toLowerCase();
    if (state.mode === "flashcard") {
      if (key === "1") {
        rateFlashcard(false);
        return;
      }
      if (key === "2") {
        rateFlashcard(true);
        return;
      }
    }
    let index = -1;
    if (/^[1-9]$/.test(key)) {
      index = Number(key) - 1;
    }
    if (index >= 0 && index < state.optionButtons.length && state.mode == "mcq") {
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
      } else if (state.mode === "flashcard") {
        rateFlashcard(true);
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
  const questionBox = document.getElementById("question-box");
  const flashcardBox = document.getElementById("flashcard-box");
  function handleBoxClick(e) {
    if (e.target.closest("button, input")) return;
    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) return;
    const box = e.currentTarget;
    const rect = box.getBoundingClientRect();
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
  }
  questionBox.addEventListener("click", handleBoxClick);
  flashcardBox.addEventListener("click", handleBoxClick);
  document.querySelectorAll(".question-selector").forEach((questionSelector) => {
    const questionNumber2 = questionSelector.querySelector(".question-number");
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
  });
}

// frontend/src/ui/reportHeight.js
function reportHeight() {
  if (document.fullscreenElement || document.documentElement.classList.contains("pseudo-fullscreen-active"))
    return;
  const pages = document.querySelectorAll(".page");
  const visible = [...pages].find((page) => page.style.display !== "none");
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
var appData = JSON.parse(document.getElementById("app-data").textContent);
var ENABLE_MATHJAX = appData.enableMathJax;
var quiz = appData.quiz;
var mode = appData.mode;
try {
  if (window.top.document.body.classList.contains("pseudo-fullscreen-active")) {
    window.top.location.reload();
  }
} catch {
}
initializeState(quiz);
loadStats();
loadQuizEdits(state);
async function initializeApp() {
  await loadMathJax(ENABLE_MATHJAX);
  if (state.mathReady && window.MathJax?.startup?.promise) {
    await window.MathJax.startup.promise;
  }
  setQuizTitle(quiz.title);
  initializeEvents();
  initHeightReporting();
  updateQuestionCounts();
  updateQuestionNumbers();
  setMode(appData.mode);
  goTo(state.currentQuestionIndex);
}
if (document.readyState === "loading") {
  window.addEventListener("load", initializeApp, { once: true });
} else {
  initializeApp();
  document.body.classList.remove("app-loading");
}
export {
  ENABLE_MATHJAX,
  mode,
  quiz
};

</script>
  </body>
</html>
"""
