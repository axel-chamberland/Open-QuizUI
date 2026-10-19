"""
title: QuizUI
author: Axel Chamberland
git_url: https://github.com/axel-chamberland/OpenQuizUI
description: This tool allows large language models to generate interactive multiple-choice quizzes and flashcards.
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


class Tools:
    class Valves(BaseModel):
        shuffle_choices: bool = Field(
            default=True,
            description="Shuffle the order of choices",
        )
        enable_mathjax: bool = Field(
            default=False,
            description=(
                "Disabled by default for privacy. Enable LaTeX/math rendering with MathJax. "
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
        request_retention: float = Field(
            default=0.9,
            ge=0.0,
            le=1.0,
            description=(
                "Target probability of recalling a card when it is scheduled for review "
                "in spaced repetition mode. "
                "Higher values generally result in shorter review intervals and more "
                "frequent reviews; lower values generally result in longer intervals "
                "and less frequent reviews."
            ),
        )
        spaced_repetition_queue_size: int = Field(
            default=20,
            ge=1,
            description=(
                "Number of questions available at a time in spaced repetition mode. "
                "Larger values provide a larger pool of questions to review before "
                "the queue needs to be replenished."
            ),
        )
        enable_spaced_repetition: bool = Field(
            default=False,
            description="Enable spaced repetition mode when the quiz loads.",
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

            if valves.quiz_mode == "flashcards":
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
                self.valves.request_retention,
                self.valves.spaced_repetition_queue_size,
                self.valves.enable_spaced_repetition,
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
    quiz,
    enable_mathjax: bool,
    light_theme="default_light",
    dark_theme="default_dark",
    default_mode="mcq",
    request_retention=0.9,
    spaced_repetition_queue_size=20,
    enable_spaced_repetition: bool = False,
):

    import json

    payload = {
        "enableMathJax": bool(enable_mathjax),
        "mode": default_mode,
        "srsQueueSize": spaced_repetition_queue_size,
        "requestRetention": request_retention,
        "srsOnLoad": bool(enable_spaced_repetition),
        "quiz": quiz,
    }

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
  padding: 0 8px 8px;
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

:is(:fullscreen, .pseudo-fullscreen-active) .title {
  display: none;
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
  visibility: hidden;
  display: block;

  margin-top: 1rem;
  padding: clamp(1.5rem, 8vw, 5rem);

  border-top: 1px solid var(--border);

  background: var(--btn);
  border: 1px solid var(--border);
  border-radius: 0.5rem;

  text-align: center;
  font-size: 1.1rem;
}

.answer-revealed .flashcard-answer {
  visibility: visible;
}

.flashcard-question {
  padding: clamp(1.5rem, 8vw, 5rem);
  margin: 0;

  background: var(--btn);
  border: 1px solid var(--border);
  border-radius: 0.5rem;

  text-align: center;
  font-size: 1.1rem;
}

.flashcard-explanation {
  visibility: hidden;
  display: block;
  margin-top: 1rem;
  padding: 0.75rem;

  background: var(--btn);

  border-radius: 0.5rem;
  font-size: 1em;
  opacity: 0.8;
}
.answer-revealed .flashcard-explanation {
  visibility: visible;
}
.flashcard-explanation:empty {
  display: none;
}

#flashcard-rating,
.fsrs-rating {
  visibility: hidden;
  display: flex;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
  border-top: 1px solid var(--border);
}

.answer-revealed #flashcard-rating {
  visibility: visible;
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
  visibility: hidden;
  display: block;
  margin-top: 1rem;
  padding: 0.75rem;
  background: var(--btn);
  border-radius: 0.5rem;
  opacity: 0.8;
}

#explanation:empty {
  display: none;
}

.answer-revealed #explanation {
  visibility: visible;
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
.question-selector,
.srs-selector {
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

.srs-mode .question-selector {
  display: none;
}

.srs-mode .next-button {
  display: none;
}

.srs-mode .srs-selector {
  display: flex;
}

.srs-selector {
  display: none;
  align-items: center;
  white-space: nowrap;

  background: var(--btn);
  color: var(--text);

  border: 1px solid var(--border);
  border-radius: 0.25rem;

  font-size: 1.1rem;

  gap: 0.7rem;
  padding: 0 0.6rem;
}

.srs-mode #flashcard-rating {
  display: none;
}

:is(:fullscreen, .pseudo-fullscreen-active) #flashcard-rating,
:is(:fullscreen, .pseudo-fullscreen-active) .fsrs-rating {
  display: none;
}

:is(:fullscreen, .pseudo-fullscreen-active) .answer-revealed #flashcard-rating {
  display: flex;
}

:is(:fullscreen, .pseudo-fullscreen-active)
  .srs-mode.answer-revealed
  #flashcard-rating {
  display: none;
}

:is(:fullscreen, .pseudo-fullscreen-active)
  .srs-mode.answer-revealed
  .fsrs-rating {
  display: flex;
}

.fsrs-rating-button {
  width: 4.5rem;
  height: 3rem;

  font-size: 1.1rem;
  line-height: 1;

  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--btn);
  color: var(--text);
  cursor: pointer;
}

.fsrs-rating-button.again-button {
  background: var(--wrong_bg);
}

.fsrs-rating-button.hard-button {
  background: color-mix(in srgb, var(--skipped) 30%, var(--btn));
}

.fsrs-rating-button.good-button {
  background: var(--correct_bg);
}

.fsrs-rating-button.easy-button {
  background: color-mix(in srgb, var(--success) 45%, var(--btn));
}

/* The rating of the card just rated, in the corner of the page. */
#rating-indicator {
  position: fixed;
  top: 8px;
  right: 8px;
  z-index: 1500;

  font-size: 1.5rem;
  line-height: 1;

  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition:
    opacity 0.4s ease,
    visibility 0.4s;
}

#rating-indicator.visible {
  opacity: 1;
  visibility: visible;
}

#rating-indicator.again {
  color: var(--danger);
}

#rating-indicator.hard {
  color: var(--skipped);
}

#rating-indicator.good,
#rating-indicator.easy {
  color: var(--success);
}
.srs-mode.answer-revealed .fsrs-rating {
  visibility: visible;
}

.srs-selector > span {
  font-variant-numeric: tabular-nums;
  cursor: default;
}

.srs-due-count {
  color: var(--skipped);
}

.srs-review-count {
  color: var(--danger);
}

.srs-completed-count {
  color: var(--success);
}

.srs-selector .current {
  text-decoration: underline;
  text-underline-offset: 0.15em;
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
#results .correct {
  color: var(--success);
}

#wrong,
#results .wrong {
  color: var(--danger);
}

#unanswered,
#results .unanswered {
  color: var(--unanswered);
}

#skipped,
#results .skipped {
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
  /* The results column is the scroller in fullscreen: a shrinkable
     chart would be squeezed by the correction sheet below it. */
  flex: 0 0 auto;
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

#editor-additional-settings {
  margin: 0.5rem 0;
}

#editor-additional-settings summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;

  cursor: pointer;
  user-select: none;

  /* The chevron below stands in for the native marker. */
  list-style: none;
}

#editor-additional-settings summary::-webkit-details-marker {
  display: none;
}

#editor-additional-settings summary svg {
  flex: 0 0 auto;

  width: 1em;
  height: 1em;

  transition: transform 0.15s ease;
}

#editor-additional-settings[open] summary svg {
  transform: rotate(90deg);
}

.editor-section {
  padding-top: 0.75rem;
}

.editor-section + .editor-section {
  margin-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.editor-section-title {
  margin: 0 0 0.5rem 0;

  font-weight: bold;
}

#editor-additional-settings .editor-settings {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 0 1.5rem;
  margin-top: 0.75rem;
}

#editor-additional-settings label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;

  padding: 0.4rem 0;
}

#editor-additional-settings label > span {
  flex: 1;
  text-align: right;
}

#editor-additional-settings input[type="number"] {
  width: 6ch;
  field-sizing: content;

  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 1rem;
  text-align: center;
}

#editor-additional-settings input[type="checkbox"] {
  accent-color: var(--success);
}

.editor-section-hint {
  margin: 0 0 0.5rem 0;

  color: var(--unanswered);
}

/* Question order overlay */
.order-editor {
  width: min(28rem, calc(100vw - 2rem));
  max-width: calc(100vw - 2rem);
  box-sizing: border-box;
}

.order-editor .order-actions {
  display: grid;
  gap: 0.35rem;

  margin-top: 0.75rem;
}

.order-editor .order-add-button {
  width: 100%;
  padding: 0.35rem 0.5rem;
  font-size: 1rem;
}

/* The row of buttons acting on the question the editor is on */
.order-editor .order-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.order-editor .order-action-row button {
  flex: 1 1 6rem;
  padding: 0.3rem 0.4rem;
  font-size: 0.9rem;
}

.order-editor .order-delete-button {
  color: var(--danger);
}

.order-editor #order-editor-list {
  display: grid;
  gap: 0.25rem;

  overflow: auto;
  overscroll-behavior: contain;

  max-height: 60vh;
  margin: 0.75rem 0;
}

.order-editor .order-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;

  min-width: max-content;
  padding: 0.35rem 0.5rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.35rem;

  /* The row is picked with a tap; dragging starts from its handle. */
  cursor: pointer;

  /*
   * The browser owns pan and pinch zoom here: touch scrolling is
   * native (smooth, both axes) and pinch zoom works. Reordering is
   * started from the row's grip handle, which claims its own gesture
   * (touch-action: none), so scrolling and dragging never conflict.
   */
  touch-action: pan-x pan-y pinch-zoom;

  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}

/* Touch drag in progress: suppress text selection and callouts */
#order-editor.dragging {
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

.order-editor .order-row:active {
  cursor: grabbing;
}

/*
 * The question that is picked: it is the one the editor is on, and the
 * one the buttons in the list act on. Marked with an inset bar and a
 * bold number rather than a border or a background, so the drag colors
 * below can still show.
 */
.order-editor .order-row.order-current {
  box-shadow: inset 3px 0 0 var(--text);
}

.order-editor .order-row.order-current .order-number {
  font-weight: 700;
}

/*
 * Visual feedback for reordered slots. The danger color marks the rows
 * the user actually dragged; the softer tint below only marks rows
 * that shifted because a neighbour was dragged past them.
 */
.order-editor .order-row.order-dragged {
  border-color: var(--danger);
  background: color-mix(in srgb, var(--danger) 18%, var(--bg));
}

.order-editor .order-row.order-changed {
  border-color: var(--skipped);
  background: color-mix(in srgb, var(--skipped) 18%, var(--bg));
}

.order-editor .order-row.order-dragging {
  opacity: 0.5;
}

.order-editor .order-row.order-drop-target {
  border-color: var(--success);
}

.order-editor .order-number {
  min-width: 2.5ch;
  text-align: right;
}

/*
 * Touch drag grip, at the left of every row. touch-action: none hands
 * it the whole gesture, so a drag started here can never lose to
 * scrolling or a native long press (the browser cannot pan a
 * touch-action: none element at all). The row body keeps native
 * scrolling and pinch zoom. It sticks to the left edge so it stays
 * reachable when a long question makes the row scroll horizontally.
 */
.order-editor .order-handle {
  flex: none;
  position: sticky;
  left: 0;

  display: flex;
  align-items: center;
  justify-content: center;

  min-width: 2.25rem;
  padding: 0.2rem 0.3rem;
  margin-left: -0.25rem;
  border-radius: 0.25rem;
  background: color-mix(in srgb, var(--border) 30%, var(--bg));
  color: var(--text);
  cursor: grab;
  font-size: 1.1em;
  line-height: 1;

  touch-action: none;

  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}

.order-editor .order-handle:active {
  cursor: grabbing;
}

.order-editor .order-caption {
  white-space: nowrap;
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

.dropdown-menu button:not(:has(svg)) {
  grid-template-columns: 1fr;
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

/*
 * A prompt can be raised from inside the order editor overlay (adding
 * or cancelling a question), and both are .global-prompt positioned
 * elements. The prompt has to stack above the overlay, not with it.
 */
#global-prompt {
  z-index: 10000;
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
        id="icon-table"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="lucide lucide-table preview-icon"
      >
        <path d="M12 3v18" />
        <rect width="18" height="18" x="3" y="3" rx="2" />
        <path d="M3 9h18" />
        <path d="M3 15h18" />
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
      <symbol
        id="icon-srs"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="lucide lucide-list-restart preview-icon"
      >
        <path d="M21 5H3" />
        <path d="M7 12H3" />
        <path d="M7 19H3" />
        <path
          d="M12 18a5 5 0 0 0 9-3 4.5 4.5 0 0 0-4.5-4.5c-1.33 0-2.54.54-3.41 1.41L11 14"
        />
        <path d="M11 10v4h4" />
      </symbol>
      <symbol
        id="icon-chevron-right"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="lucide lucide-chevron-right"
      >
        <path d="m9 18 6-6-6-6" />
      </symbol>
    </svg>
    <div id="rating-indicator" aria-hidden="true"></div>
    <div id="global-prompt" class="global-prompt">
      <p id="global-prompt-message"></p>
      <div class="button-row">
        <button id="global-prompt-yes">yes</button>
        <button id="global-prompt-no">no</button>
      </div>
    </div>
    <div id="order-editor" class="global-prompt order-editor">
      <p><strong>Questions</strong></p>
      <div class="order-actions">
        <button id="order-editor-add" class="order-add-button">
          + Add question
        </button>
        <div class="order-action-row">
          <button
            id="order-editor-add-before"
            title="Add a new question before the current one"
          >
            Add before
          </button>
          <button
            id="order-editor-add-after"
            title="Add a new question after the current one"
          >
            Add after
          </button>
          <button
            id="order-editor-delete"
            class="order-delete-button"
            title="Delete the current question"
          >
            Delete question
          </button>
        </div>
      </div>
      <div id="order-editor-list"></div>
      <div class="button-row">
        <button id="order-editor-cancel">Cancel</button>
        <button id="order-editor-save">Save</button>
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
          <div class="srs-selector">
            <span class="srs-due-count" title="Due"></span>
            <span class="srs-review-count" title="Reviewing"></span>
            <span class="srs-completed-count" title="Completed"></span>
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
          title="Edit Question"
          aria-label="Edit Question"
        >
          <svg><use href="#icon-editor"></use></svg>
          Edit Question
        </button>
        <button
          class="toggle-srs-button"
          title="Toggle spaced repetition (FSRS)"
          aria-label="Toggle spaced repetition (FSRS)"
        >
          <svg><use href="#icon-srs"></use></svg>
          Toggle Repetition
        </button>
        <button
          class="download-button"
          title="Download as HTML"
          aria-label="Download as HTML"
        >
          <svg><use href="#icon-download"></use></svg>
          Download HTML
        </button>
        <button
          class="copy-all-button"
          title="Copy quiz"
          aria-label="Copy quiz"
        >
          <svg><use href="#icon-copy-all"></use></svg>Copy Quiz
        </button>
        <button
          class="copy-flashcards-button"
          title="Copy as flashcards"
          aria-label="Copy as flashcards"
        >
          <svg><use href="#icon-table"></use></svg>
          Copy as Flashcards
        </button>
      </div>
      <div id="question-scroll">
        <p id="question"></p>
        <div id="options"></div>
        <div id="explanation"></div>
      </div>
      <div class="fsrs-rating button-row">
        <button class="fsrs-rating-button again-button" data-rating="1">
          Again
        </button>
        <button class="fsrs-rating-button hard-button" data-rating="2">
          Hard
        </button>
        <button class="fsrs-rating-button good-button" data-rating="3">
          Good
        </button>
        <button class="fsrs-rating-button easy-button" data-rating="4">
          Easy
        </button>
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
          <div class="srs-selector">
            <span class="srs-due-count" title="Due"></span>
            <span class="srs-review-count" title="Reviewing"></span>
            <span class="srs-completed-count" title="Completed"></span>
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
          title="Edit Question"
          aria-label="Edit Question"
        >
          <svg><use href="#icon-editor"></use></svg>
          Edit Question
        </button>
        <button
          class="toggle-srs-button"
          title="Toggle spaced repetition (FSRS)"
          aria-label="Toggle spaced repetition (FSRS)"
        >
          <svg><use href="#icon-srs"></use></svg>
          Toggle Repetition
        </button>
        <button
          class="download-button"
          title="Download as HTML"
          aria-label="Download as HTML"
        >
          <svg><use href="#icon-download"></use></svg>
          Download HTML
        </button>
        <button
          class="copy-all-button"
          title="Copy quiz"
          aria-label="Copy quiz"
        >
          <svg><use href="#icon-copy-all"></use></svg>Copy Quiz
        </button>
        <button
          class="copy-flashcards-button"
          title="Copy as flashcards"
          aria-label="Copy as flashcards"
        >
          <svg><use href="#icon-table"></use></svg>
          Copy as Flashcards
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

      <div class="fsrs-rating button-row">
        <button class="fsrs-rating-button again-button" data-rating="1">
          Again
        </button>
        <button class="fsrs-rating-button hard-button" data-rating="2">
          Hard
        </button>
        <button class="fsrs-rating-button good-button" data-rating="3">
          Good
        </button>
        <button class="fsrs-rating-button easy-button" data-rating="4">
          Easy
        </button>
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
            title="Download as HTML"
            aria-label="Download as HTML"
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
        <p id="editor-question-number"></p>
        <p><strong>Title:</strong></p>
        <div id="editor-title"></div>
        <details id="editor-additional-settings">
          <summary>
            <svg><use href="#icon-chevron-right"></use></svg>
            Additional Settings
          </summary>
          <div class="editor-section">
            <p class="editor-section-title">Review Scheduling (FSRS)</p>
            <div class="editor-settings">
              <label>
                <span>Spaced repetition queue size:</span>
                <input
                  type="number"
                  id="editor-srs-queue-size"
                  min="1"
                  step="1"
                />
              </label>
              <label>
                <span>Request retention:</span>
                <input
                  type="number"
                  id="editor-fsrs-request-retention"
                  min="0.01"
                  max="0.99"
                  step="0.01"
                />
              </label>
              <label>
                <span>Maximum interval (days):</span>
                <input
                  type="number"
                  id="editor-fsrs-maximum-interval"
                  min="1"
                  step="1"
                />
              </label>
              <label class="editor-settings-toggle">
                <span>Enable fuzz:</span>
                <input type="checkbox" id="editor-fsrs-enable-fuzz" />
              </label>
              <label class="editor-settings-toggle">
                <span>Enable short-term scheduling:</span>
                <input type="checkbox" id="editor-fsrs-enable-short-term" />
              </label>
            </div>
          </div>
          <div class="editor-section">
            <p class="editor-section-title">Questions</p>
            <p class="editor-section-hint">
              Select, add, remove or reorder questions.
            </p>
            <button id="order-editor-open-button">Edit Questions</button>
          </div>
        </details>
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
function getStoredQuestionIndex(quizStorageKey, max_count) {
  try {
    const index = Number(localStorage.getItem(getProgressKey(quizStorageKey)));
    if (!Number.isInteger(index)) {
      return 0;
    }
    return Math.max(0, Math.min(index, max_count));
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

// frontend/src/persistence/question_order.js
function loadQuestionOrder(quizStorageKey, questionCount, removedIndexes = null) {
  const removed = removedIndexes ?? /* @__PURE__ */ new Set();
  let stored = null;
  try {
    const data = JSON.parse(
      localStorage.getItem(`questionOrder_${quizStorageKey}`)
    );
    if (Array.isArray(data)) {
      stored = data;
    }
  } catch {
  }
  if (!stored) {
    return Array.from({ length: questionCount }, (_, index) => index).filter(
      (index) => !removed.has(index)
    );
  }
  const order = [];
  const seen = /* @__PURE__ */ new Set();
  for (const index of stored) {
    const valid = Number.isInteger(index) && index >= 0 && index < questionCount && !seen.has(index) && !removed.has(index);
    if (valid) {
      seen.add(index);
      order.push(index);
    }
  }
  for (let index = 0; index < questionCount; index++) {
    if (!seen.has(index) && !removed.has(index)) {
      order.push(index);
    }
  }
  return order;
}
function saveQuestionOrder(quizStorageKey, questionOrder) {
  try {
    localStorage.setItem(
      `questionOrder_${quizStorageKey}`,
      JSON.stringify(questionOrder)
    );
  } catch {
  }
}
function clearQuestionOrder(quizStorageKey) {
  try {
    localStorage.removeItem(`questionOrder_${quizStorageKey}`);
  } catch {
  }
}
function loadQuestionSRSState(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(`questionSRSQueue_${quizStorageKey}`)
    );
    if (data && typeof data === "object" && Array.isArray(data.queue)) {
      return {
        score: data.score ?? 0,
        queue: data.queue
      };
    }
  } catch {
  }
  return null;
}
function saveQuestionSRSState(quizStorageKey, srsState) {
  try {
    localStorage.setItem(
      `questionSRSQueue_${quizStorageKey}`,
      JSON.stringify(srsState)
    );
  } catch {
  }
}
function resetQuestionSRSState(quizStorageKey) {
  try {
    localStorage.removeItem(`questionSRSQueue_${quizStorageKey}`);
  } catch {
  }
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
    appendStoredQuestions(edits);
  } catch (e) {
    console.error("Failed to load quiz edits:", e);
  }
}
function appendStoredQuestions(edits) {
  const pending = Object.entries(edits).map(([index, question]) => [Number(index), question]).filter(([index]) => Number.isInteger(index) && index >= 0).sort(([a], [b]) => a - b);
  for (const [index, question] of pending) {
    if (index < state.quiz.questions.length) {
      continue;
    }
    while (state.quiz.questions.length < index) {
      appendQuestion(createQuestionTemplate());
    }
    appendQuestion(question);
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
function removeLocalEditAndShift(index) {
  const key = getQuizEditsKey(state.quizStorageKey);
  let edits;
  try {
    edits = JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return false;
  }
  const shifted = {};
  for (const [storedIndex, value] of Object.entries(edits)) {
    if (storedIndex === "title") {
      shifted.title = value;
      continue;
    }
    const i = Number(storedIndex);
    if (!Number.isInteger(i) || i === index) {
      continue;
    }
    shifted[i > index ? i - 1 : i] = value;
  }
  try {
    if (Object.keys(shifted).length === 0) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(shifted));
    }
  } catch (e) {
    console.error("Failed to update edits:", e);
    return false;
  }
  return true;
}

// frontend/src/persistence/question_removals.js
function getQuestionRemovalsKey(quizStorageKey) {
  return `questionRemovals_${quizStorageKey}`;
}
function loadQuestionRemovals(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(getQuestionRemovalsKey(quizStorageKey))
    );
    if (Array.isArray(data)) {
      return new Set(data.filter(Number.isInteger));
    }
  } catch {
  }
  return /* @__PURE__ */ new Set();
}
function saveQuestionRemovals(quizStorageKey, indexes) {
  const key = getQuestionRemovalsKey(quizStorageKey);
  try {
    if (indexes.size === 0) {
      localStorage.removeItem(key);
      return;
    }
    localStorage.setItem(key, JSON.stringify(Array.from(indexes)));
  } catch {
  }
}
function clearQuestionRemovals(quizStorageKey) {
  try {
    localStorage.removeItem(getQuestionRemovalsKey(quizStorageKey));
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
  questionOrder: [],
  questionSRSQueue: null,
  srs: false,
  srsQueueSize: 20,
  /*
   * Number of questions the quiz itself has. Every question from here
   * on was added in the editor.
   */
  builtInQuestionCount: 0,
  /*
   * Indexes of the quiz's own questions deleted in the editor. They
   * stay in state.quiz.questions - see deleteQuestion - but are left
   * out of the navigation order.
   */
  removedQuestions: /* @__PURE__ */ new Set(),
  /*
   * FSRS scheduler parameters; see srs.js. Values may be changed
   * per-quiz in the editor's additional settings.
   */
  srsConfig: {
    request_retention: 0.9,
    maximum_interval: 365,
    enable_fuzz: true,
    enable_short_term: true
  },
  // Maximum level before removing from queue
  srsLevel: 5,
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
function createQuestionTemplate() {
  const questions = state.quiz.questions;
  const reference = questions[state.currentQuestionIndex] ?? questions[questions.length - 1];
  const optionCount = reference?.options?.length || 2;
  return {
    question: "",
    options: new Array(optionCount).fill(""),
    correct_index: 0,
    explanation: ""
  };
}
function appendQuestion(question) {
  const index = state.quiz.questions.length;
  state.quiz.questions.push(question);
  state.questionOrder.push(index);
  state.questionResults[index] = UNANSWERED;
  state.questionAnswers[index] = null;
  return index;
}
function removeAppendedQuestion(index) {
  state.quiz.questions.splice(index, 1);
  state.questionResults.splice(index, 1);
  state.questionAnswers.splice(index, 1);
  state.questionOrder = state.questionOrder.filter((item) => item !== index).map((item) => item > index ? item - 1 : item);
}
function initializeState(quiz2) {
  state.quiz = quiz2;
  state.quizStorageKey = hashQuiz(quiz2);
  state.builtInQuestionCount = quiz2.questions.length;
  state.removedQuestions = loadQuestionRemovals(state.quizStorageKey);
  loadQuizEdits(state);
  state.currentQuestion = null;
  state.optionButtons = [];
  state.wrongAnswerCount = 0;
  state.answerRevealed = false;
  state.questionOrder = loadQuestionOrder(
    state.quizStorageKey,
    state.quiz.questions.length,
    state.removedQuestions
  );
  state.currentQuestionIndex = getStoredQuestionIndex(
    state.quizStorageKey,
    state.quiz.questions.length
  );
  if (state.removedQuestions.has(state.currentQuestionIndex)) {
    state.currentQuestionIndex = state.questionOrder[0] ?? 0;
  }
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
async function renderMCQ() {
  const questionBox = document.getElementById("question-box");
  const questionText = questionBox.querySelector("#question");
  const optionsContainer = document.getElementById("options");
  const explanationEl = document.getElementById("explanation");
  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    document.getElementById("question").textContent = "No valid questions parsed";
    return;
  }
  const question = state.quiz.questions[state.currentQuestionIndex];
  state.currentQuestion = question;
  renderQuestion(questionText, question);
  explanationEl.innerHTML = question.explanation ? renderMarkdown(question.explanation, state.mathReady) : "";
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
function padToQuestionCount(values, fallback) {
  const padded = values.slice(0, state.quiz.questions.length);
  while (padded.length < state.quiz.questions.length) {
    padded.push(fallback);
  }
  return padded;
}
function loadStats() {
  try {
    const data = JSON.parse(
      localStorage.getItem(getStatsKey(state.quizStorageKey))
    );
    if (Array.isArray(data?.results)) {
      state.questionResults = padToQuestionCount(data.results, UNANSWERED);
    }
    if (Array.isArray(data?.answers)) {
      state.questionAnswers = padToQuestionCount(data.answers, null);
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
  const questionText = toMarkdown(question.question);
  lines.push(`Question ${index + 1}: ${questionText}`);
  lines.push("");
  for (const [i, option] of question.options.entries()) {
    const letter = String.fromCharCode(65 + i);
    lines.push(`${letter}. ${toMarkdown(option)}`);
  }
  return lines.join("\n");
}
function escapeTableCell(text) {
  return String(text ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
}
function formatAnswerKey(questions) {
  const lines = [
    "Answer Key:",
    "",
    "| Question | Correct Answer | Explanation |",
    "| --- | --- | --- |"
  ];
  for (const [index, question] of questions.entries()) {
    const correctLetter = String.fromCharCode(65 + question.correct_index);
    const explanation = toMarkdown(question.explanation || "");
    lines.push(
      `| ${index + 1} | ${correctLetter} | ${escapeTableCell(explanation)} |`
    );
  }
  return lines.join("\n");
}
function formatQuizAsText(quiz2) {
  const lines = [toMarkdown(quiz2.title), ""];
  for (const [index, question] of quiz2.questions.entries()) {
    lines.push(formatQuestionAsText(question, index));
    lines.push("");
  }
  lines.push(formatAnswerKey(quiz2.questions));
  return lines.join("\n").trim();
}
function formatQuizAsFlashcards(quiz2) {
  const lines = [
    toMarkdown(quiz2.title),
    "",
    "| Question | Answer | Explanation |",
    "| --- | --- | --- |"
  ];
  for (const question of quiz2.questions) {
    const answerIndex = question.options.length === 1 ? 0 : question.correct_index;
    const questionText = escapeTableCell(toMarkdown(question.question));
    const answer = escapeTableCell(
      toMarkdown(question.options[answerIndex] ?? "")
    );
    const explanation = escapeTableCell(toMarkdown(question.explanation || ""));
    lines.push(`| ${questionText} | ${answer} | ${explanation} |`);
  }
  return lines.join("\n").trim();
}

// frontend/src/srs.js
function getSRSConfig() {
  return {
    request_retention: state.srsConfig.request_retention,
    maximum_interval: state.srsConfig.maximum_interval,
    enable_fuzz: state.srsConfig.enable_fuzz,
    enable_short_term: state.srsConfig.enable_short_term
  };
}
var VALID_RATINGS = /* @__PURE__ */ new Set(["Again", "Hard", "Good", "Easy"]);
var fsrsPromise = null;
var fsrsModule = null;
var scheduler = null;
var cards = /* @__PURE__ */ new Map();
var history = [];
async function loadFSRS() {
  if (scheduler) return true;
  if (!fsrsPromise) {
    fsrsPromise = import("https://cdn.jsdelivr.net/npm/ts-fsrs@5.4.2/+esm");
  }
  try {
    fsrsModule = await fsrsPromise;
    scheduler = fsrsModule.fsrs(getSRSConfig());
    return true;
  } catch (error) {
    console.error("Failed to import FSRS:", error);
    fsrsPromise = null;
    fsrsModule = null;
    scheduler = null;
    return false;
  }
}
function restoreCard(card) {
  return {
    ...card,
    due: new Date(card.due),
    last_review: card.last_review ? new Date(card.last_review) : void 0
  };
}
function compareSRSItems(a, b) {
  const aDue = new Date(a.card.due).getTime();
  const bDue = new Date(b.card.due).getTime();
  if (aDue !== bDue) {
    return aDue - bDue;
  }
  return a.index - b.index;
}
function sortSRSQueue() {
  state.questionSRSQueue.sort(compareSRSItems);
}
function saveSRS(quizStorageKey) {
  const active = new Set(state.questionSRSQueue.map(({ index }) => index));
  saveQuestionSRSState(quizStorageKey, {
    queue: Array.from(cards, ([index, card]) => ({
      index,
      card,
      active: active.has(index)
    }))
  });
}
function addNewSRSQuestion() {
  const queue = state.questionSRSQueue;
  if (queue.length >= state.srsQueueSize) {
    return null;
  }
  const active = new Set(queue.map(({ index: index2 }) => index2));
  const index = state.questionOrder.find(
    (questionIndex) => !cards.has(questionIndex) && !active.has(questionIndex)
  );
  if (index === void 0) {
    return null;
  }
  const card = fsrsModule.createEmptyCard();
  cards.set(index, card);
  queue.push({
    index,
    card
  });
  return index;
}
function addNextSRSQuestion() {
  return addNewSRSQuestion();
}
function setSRSConfig(config) {
  Object.assign(state.srsConfig, config);
  if (fsrsModule) {
    scheduler = fsrsModule.fsrs(getSRSConfig());
  }
}
async function initSRS(quizStorageKey, currentQuestionIndex) {
  if (!await loadFSRS()) {
    return false;
  }
  history.length = 0;
  cards.clear();
  state.questionSRSQueue = [];
  const savedState = loadQuestionSRSState(quizStorageKey);
  if (savedState) {
    const validIndices = new Set(state.questionOrder);
    for (const item of savedState.queue) {
      if (!validIndices.has(item.index) || !item.card || cards.has(item.index)) {
        continue;
      }
      const card = restoreCard(item.card);
      cards.set(item.index, card);
      if (item.active !== false && state.questionSRSQueue.length < state.srsQueueSize) {
        state.questionSRSQueue.push({
          index: item.index,
          card
        });
      }
    }
  }
  if (!savedState && state.questionOrder.includes(currentQuestionIndex)) {
    const card = fsrsModule.createEmptyCard();
    cards.set(currentQuestionIndex, card);
    state.questionSRSQueue.push({
      index: currentQuestionIndex,
      card
    });
  }
  const initialSize = Math.min(state.srsQueueSize, state.questionOrder.length);
  while (state.questionSRSQueue.length < initialSize) {
    if (addNextSRSQuestion() === null) {
      break;
    }
  }
  sortSRSQueue();
  saveSRS(quizStorageKey);
  return true;
}
function nextSRSQuestion() {
  return state.questionSRSQueue[0]?.index ?? null;
}
async function updateSRS(rating, quizStorageKey) {
  if (!VALID_RATINGS.has(rating)) {
    return false;
  }
  await loadFSRS();
  const queue = state.questionSRSQueue;
  if (!queue?.length) {
    return false;
  }
  const questionIndex = state.currentQuestionIndex;
  const position = queue.findIndex(({ index }) => index === questionIndex);
  if (position === -1) {
    return false;
  }
  const item = queue[position];
  const previousQueue = queue.map(({ index }) => index);
  const fsrsRating = fsrsModule.Rating[rating];
  const result = scheduler.next(item.card, /* @__PURE__ */ new Date(), fsrsRating);
  item.card = result.card;
  cards.set(questionIndex, result.card);
  const change = {
    questionIndex,
    reviewLog: result.log,
    previousQueue,
    addedIndices: [],
    quizStorageKey
  };
  if (result.card.state === fsrsModule.State.Review) {
    queue.splice(position, 1);
    const addedIndex = addNewSRSQuestion();
    if (addedIndex !== null) {
      change.addedIndices.push(addedIndex);
    }
  }
  sortSRSQueue();
  history.push(change);
  saveSRS(quizStorageKey);
  return true;
}
function prevSRSQuestion(quizStorageKey) {
  const change = history.at(-1);
  if (!change) {
    return null;
  }
  if (change.quizStorageKey !== quizStorageKey) {
    return null;
  }
  history.pop();
  for (const index of change.addedIndices) {
    cards.delete(index);
  }
  const card = cards.get(change.questionIndex);
  if (card) {
    const previousCard = scheduler.rollback(card, change.reviewLog);
    cards.set(change.questionIndex, previousCard);
  }
  state.questionSRSQueue = change.previousQueue.map((index) => {
    const card2 = cards.get(index);
    if (!card2) {
      return null;
    }
    return {
      index,
      card: card2
    };
  }).filter(Boolean);
  sortSRSQueue();
  saveSRS(quizStorageKey);
  return change.questionIndex;
}
function removeQuestionFromSRS(index, shiftIndexes = true) {
  const shift = (i) => shiftIndexes && i > index ? i - 1 : i;
  const saved = loadQuestionSRSState(state.quizStorageKey);
  if (saved) {
    saveQuestionSRSState(state.quizStorageKey, {
      score: saved.score,
      queue: saved.queue.filter((item) => item.index !== index).map((item) => ({ ...item, index: shift(item.index) }))
    });
  }
  if (cards.size === 0 && !state.questionSRSQueue?.length) {
    return;
  }
  const shifted = /* @__PURE__ */ new Map();
  for (const [cardIndex, card] of cards) {
    if (cardIndex !== index) {
      shifted.set(shift(cardIndex), card);
    }
  }
  cards.clear();
  for (const [cardIndex, card] of shifted) {
    cards.set(cardIndex, card);
  }
  state.questionSRSQueue = (state.questionSRSQueue ?? []).filter((item) => item.index !== index).map((item) => ({ ...item, index: shift(item.index) }));
  history.length = 0;
  saveSRS(state.quizStorageKey);
}
function getSRSCounts() {
  const total = state.questionOrder.length;
  const due = state.questionOrder.filter((index) => {
    const card = cards.get(index);
    return !card?.last_review;
  }).length;
  const reviewing = state.questionSRSQueue.filter(({ card }) => {
    return card.last_review;
  }).length;
  const completed = total - due - reviewing;
  return {
    due,
    reviewing,
    completed
  };
}
function getSRSCurrentCategory() {
  const currentIndex = state.currentQuestionIndex;
  const card = cards.get(currentIndex);
  if (!card?.last_review) {
    return "due";
  }
  const isInQueue = state.questionSRSQueue.some(
    ({ index }) => index === currentIndex
  );
  return isInQueue ? "reviewing" : "completed";
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

// frontend/src/ui/rating_indicator.js
var RATINGS = {
  Again: { icon: "\u2717", className: "again" },
  Hard: { icon: "\u2713", className: "hard" },
  Good: { icon: "\u2713", className: "good" },
  Easy: { icon: "\u2713\u2713", className: "easy" }
};
var VISIBLE_MS = 2e3;
var hideTimer = null;
function showRatingIndicator(rating) {
  const indicator = document.getElementById("rating-indicator");
  const entry = RATINGS[rating];
  if (!indicator || !entry) {
    return;
  }
  for (const { className } of Object.values(RATINGS)) {
    indicator.classList.remove(className);
  }
  indicator.textContent = entry.icon;
  indicator.classList.add(entry.className, "visible");
  clearTimeout(hideTimer);
  hideTimer = setTimeout(hideRatingIndicator, VISIBLE_MS);
}
function hideRatingIndicator() {
  clearTimeout(hideTimer);
  hideTimer = null;
  document.getElementById("rating-indicator")?.classList.remove("visible");
}

// frontend/src/rendering/flashcards.js
async function renderFlashcard() {
  const flashcardBox = document.getElementById("flashcard-box");
  const questionText = flashcardBox.querySelector(".flashcard-question");
  const answerEl = flashcardBox.querySelector(".flashcard-answer");
  const explanationEl = flashcardBox.querySelector(".flashcard-explanation");
  if (!state.quiz.questions || state.quiz.questions.length === 0) {
    questionText.textContent = "No valid questions parsed";
    return;
  }
  const questionArrayIndex = getCurrentQuestionArrayIndex();
  const question = state.quiz.questions[questionArrayIndex];
  state.currentQuestion = question;
  renderQuestion(questionText, question);
  const answerIndex = question.options.length === 1 ? 0 : question.correct_index;
  answerEl.innerHTML = renderMarkdown(
    question.options[answerIndex],
    state.mathReady
  );
  explanationEl.innerHTML = question.explanation ? renderMarkdown(question.explanation, state.mathReady) : "";
  state.answerRevealed = false;
  updateNavigation();
  flashcardBox.querySelector("#flashcard-scroll").scrollTop = 0;
  await typesetMath();
}
async function rateFlashcard(correct) {
  if (!state.answerRevealed) {
    return;
  }
  const questionArrayIndex = getCurrentQuestionArrayIndex();
  state.questionResults[questionArrayIndex] = correct ? CORRECT : WRONG;
  saveStats();
  nextQuestion();
  showRatingIndicator(correct ? "Good" : "Again");
}

// frontend/src/rendering/results.js
async function renderResults() {
  const results = document.getElementById("results");
  const flashcardBox = document.getElementById("flashcard-box");
  flashcardBox.style.display = "none";
  const questionBox = document.getElementById("question-box");
  questionBox.style.display = "none";
  results.style.display = "";
  const ordered = state.questionOrder.map(
    (index) => state.questionResults[index]
  );
  const correct = ordered.filter((x) => x === CORRECT).length;
  const wrong = ordered.filter((x) => x === WRONG).length;
  const unanswered = ordered.filter((x) => x === UNANSWERED).length;
  const skipped = ordered.filter((x) => x === SKIPPED).length;
  const total = state.questionOrder.length;
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
  for (let orderIndex = 0; orderIndex < state.questionOrder.length; orderIndex++) {
    const index = state.questionOrder[orderIndex];
    const question = questions[index];
    const correctAnswer = question.options[question.correct_index];
    const userIndex = state.questionAnswers[index];
    const userAnswer = state.mode === "flashcard" ? state.questionResults[index] === CORRECT ? "\u2713" : state.questionResults[index] === WRONG ? "\u2717" : "Unanswered" : state.questionResults[index] === SKIPPED ? "Skipped" : userIndex !== null ? question.options[userIndex] : "Unanswered";
    const article = document.createElement("article");
    const currentClass = resultClass[state.questionResults[index]];
    article.innerHTML = `
<h3 class="${currentClass}">Question ${orderIndex + 1}</h3>

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
async function restartQuiz() {
  state.currentQuestionIndex = state.questionOrder[0];
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
  setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
  resetQuestionSRSState(state.quizStorageKey);
  if (state.srs) {
    await initSRS(state.quizStorageKey, state.currentQuestionIndex);
  }
  const results = document.getElementById("results");
  results.style.display = "none";
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

// frontend/src/persistence/app_data.js
function loadAppData() {
  const appData2 = JSON.parse(document.getElementById("app-data").textContent);
  return { ...appData2, ...getStoredAppDataOverrides(hashQuiz(appData2.quiz)) };
}
function getAppDataOverridesKey(quizStorageKey) {
  return `appDataOverrides_${quizStorageKey}`;
}
function getStoredAppDataOverrides(quizStorageKey) {
  try {
    const data = JSON.parse(
      localStorage.getItem(getAppDataOverridesKey(quizStorageKey))
    );
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return data;
    }
  } catch {
  }
  return {};
}
function saveAppDataOverrides(quizStorageKey, overrides) {
  if (!quizStorageKey) {
    return;
  }
  try {
    const stored = getStoredAppDataOverrides(quizStorageKey);
    localStorage.setItem(
      getAppDataOverridesKey(quizStorageKey),
      JSON.stringify({ ...stored, ...overrides })
    );
  } catch {
  }
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
    document.removeEventListener("keydown", keyHandler2, true);
    if (callback) callback();
  };
  yesButton.onclick = () => close(onYes);
  noButton.onclick = () => close(onNo);
  function keyHandler2(e) {
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
  document.addEventListener("keydown", keyHandler2, true);
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
    document.removeEventListener("keydown", keyHandler2, true);
  };
  yesButton.onclick = close;
  function keyHandler2(e) {
    if (e.key === "Enter" || e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
    }
  }
  document.addEventListener("keydown", keyHandler2, true);
  prompt.classList.add("visible");
}

// frontend/src/quiz.js
function hideResults() {
  document.getElementById("results").style.display = "none";
}
function isResultsVisible() {
  return document.getElementById("results").style.display !== "none";
}
function getCurrentQuestionArrayIndex() {
  return state.currentQuestionIndex;
}
async function nextQuestion() {
  if (state.srs) {
    const questionIndex2 = nextSRSQuestion();
    if (questionIndex2 === null) {
      renderResults();
      return;
    }
    goTo(questionIndex2);
    return;
  }
  const currentOrderIndex = state.questionOrder.indexOf(
    state.currentQuestionIndex
  );
  if (currentOrderIndex === -1) {
    return;
  }
  const questionIndex = state.questionOrder[currentOrderIndex + 1];
  if (questionIndex === void 0) {
    renderResults();
    return;
  }
  goTo(questionIndex);
}
function prevQuestion() {
  if (state.srs) {
    const questionIndex = prevSRSQuestion(state.quizStorageKey);
    if (questionIndex === null) {
      return;
    }
    hideRatingIndicator();
    hideResults();
    goTo(questionIndex);
    return;
  }
  if (isResultsVisible()) {
    const lastOrderIndex = state.questionOrder.length - 1;
    if (lastOrderIndex < 0) {
      return;
    }
    hideResults();
    goTo(state.questionOrder[lastOrderIndex]);
    return;
  }
  const currentOrderIndex = state.questionOrder.indexOf(
    state.currentQuestionIndex
  );
  if (currentOrderIndex <= 0) {
    return;
  }
  hideResults();
  goTo(state.questionOrder[currentOrderIndex - 1]);
}
function goTo(questionIndex) {
  if (questionIndex < 0) {
    questionIndex = 0;
  }
  state.currentQuestionIndex = questionIndex;
  if (questionIndex >= state.quiz.questions.length) {
    renderResults();
    return;
  }
  state.currentQuestion = state.quiz.questions[questionIndex];
  state.answerRevealed = false;
  if (!state.srs) {
    setStoredQuestionIndex(state.quizStorageKey, questionIndex);
  }
  updateQuestionNumbers();
  renderCurrentQuestionView();
}
function goToPosition(position) {
  if (!Number.isFinite(position) || position < 1) {
    position = 1;
  }
  const questionIndex = state.srs ? position - 1 : state.questionOrder[position - 1];
  if (questionIndex === void 0) {
    goTo(state.quiz.questions.length);
    return;
  }
  goTo(questionIndex);
}
function renderCurrentQuestionView() {
  const question = state.currentQuestion;
  let mode2 = state.mode;
  if (mode2 === "flashcard" || question.options.length < 2) {
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
    if (state.srs) {
      element.value = state.currentQuestionIndex + 1;
      return;
    }
    element.value = state.questionOrder.indexOf(state.currentQuestionIndex) + 1;
  });
}
function updateQuestionCounts() {
  document.querySelectorAll(".question-count").forEach((element) => {
    element.textContent = state.questionOrder.length;
  });
}
function addQuestion(orderPosition = null) {
  const index = appendQuestion(createQuestionTemplate());
  if (orderPosition !== null) {
    state.questionOrder.splice(state.questionOrder.indexOf(index), 1);
    state.questionOrder.splice(orderPosition, 0, index);
  }
  saveLocalEdit(index, false);
  saveQuestionOrder(state.quizStorageKey, state.questionOrder);
  updateQuestionNumbers();
  updateQuestionCounts();
  if (state.srs) {
    updateSRSCounts();
  }
  return index;
}
function removeAddedQuestion(index) {
  removeLocalEditAndShift(index);
  removeQuestionFromSRS(index);
  removeAppendedQuestion(index);
  saveQuestionOrder(state.quizStorageKey, state.questionOrder);
  updateQuestionNumbers();
  updateQuestionCounts();
  if (state.srs) {
    updateSRSCounts();
  }
}
function deleteQuestion(index) {
  if (index >= state.builtInQuestionCount) {
    removeAddedQuestion(index);
    return;
  }
  state.removedQuestions.add(index);
  removeLocalEdit(index);
  removeQuestionFromSRS(index, false);
  state.questionOrder = state.questionOrder.filter((item) => item !== index);
  saveQuestionRemovals(state.quizStorageKey, state.removedQuestions);
  saveQuestionOrder(state.quizStorageKey, state.questionOrder);
  updateQuestionNumbers();
  updateQuestionCounts();
  if (state.srs) {
    updateSRSCounts();
  }
}
async function handleAnswer(index, button) {
  saveStats();
  const questionArrayIndex = getCurrentQuestionArrayIndex();
  if (index === state.currentQuestion.correct_index) {
    revealAnswer();
    if (state.wrongAnswerCount === 0) {
      state.questionResults[questionArrayIndex] = CORRECT;
      state.questionAnswers[questionArrayIndex] = index;
      saveStats();
    }
  } else {
    button.classList.add("wrong");
    button.disabled = true;
    state.questionResults[questionArrayIndex] = WRONG;
    if (state.questionAnswers[questionArrayIndex] === null) {
      state.questionAnswers[questionArrayIndex] = index;
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
  const questionArrayIndex = getCurrentQuestionArrayIndex();
  state.optionButtons.forEach((btn) => btn.disabled = true);
  if (state.questionResults[questionArrayIndex] === UNANSWERED) {
    state.questionResults[questionArrayIndex] = SKIPPED;
    saveStats();
  }
  document.body.classList.add("answer-revealed");
  if (document.getElementById("question-box").style.display === "none") {
    return;
  }
  const optionsContainer = document.getElementById("options");
  const buttons = optionsContainer.querySelectorAll("button");
  buttons[state.currentQuestion.correct_index].classList.add("correct");
}
async function rateFSRS(rating) {
  if (!state.answerRevealed) {
    return;
  }
  const questionArrayIndex = getCurrentQuestionArrayIndex();
  const ratingNames = {
    1: "Again",
    2: "Hard",
    3: "Good",
    4: "Easy"
  };
  state.questionResults[questionArrayIndex] = rating === 1 ? WRONG : CORRECT;
  await updateSRS(ratingNames[rating], state.quizStorageKey);
  saveStats();
  showRatingIndicator(ratingNames[rating]);
}
function setQuizTitle(title) {
  const displayTitle = title.slice(0, 60);
  document.title = displayTitle;
  document.querySelectorAll(".title").forEach((e) => {
    e.textContent = title;
  });
}
function renderQuestion(questionText, question) {
  document.body.classList.remove("answer-revealed");
  questionText.innerHTML = renderMarkdown(question.question, state.mathReady);
  if (state.srs) {
    updateSRSCounts();
  }
}
function updateSRSCounts() {
  const { due, reviewing, completed } = getSRSCounts();
  const currentCategory = getSRSCurrentCategory();
  document.querySelectorAll(".srs-due-count").forEach((element) => {
    element.textContent = String(due);
    element.classList.toggle("current", currentCategory === "due");
  });
  document.querySelectorAll(".srs-review-count").forEach((element) => {
    element.textContent = String(reviewing);
    element.classList.toggle("current", currentCategory === "reviewing");
  });
  document.querySelectorAll(".srs-completed-count").forEach((element) => {
    element.textContent = String(completed);
    element.classList.toggle("current", currentCategory === "completed");
  });
}
function updateNavigation() {
  document.querySelectorAll(".prev-button").forEach((button) => {
    if (state.srs) {
      button.disabled = false;
      return;
    }
    button.disabled = state.questionOrder.indexOf(state.currentQuestionIndex) <= 0;
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
  saveAppDataOverrides(state.quizStorageKey, { mode: state.mode });
  if (state.mode === "mcq") {
    renderMCQ();
  } else {
    renderFlashcard();
  }
}
async function toggleSRS() {
  if (!state.srs) {
    const initialized = await initSRS(
      state.quizStorageKey,
      state.currentQuestionIndex
    );
    if (!initialized) {
      showAlert(
        "Unable to load the FSRS library from the CDN. If it is not already cached, an internet connection is required. Please check your connection and try again."
      );
      return;
    }
  }
  state.srs = !state.srs;
  saveAppDataOverrides(state.quizStorageKey, { srsOnLoad: state.srs });
  if (!state.srs) {
    setStoredQuestionIndex(state.quizStorageKey, state.currentQuestionIndex);
  }
  document.body.classList.toggle("srs-mode", state.srs);
  updateQuestionNumbers();
  if (state.srs) {
    updateSRSCounts();
    const questionIndex = nextSRSQuestion();
    if (questionIndex !== null) {
      goTo(questionIndex);
    }
  }
}

// frontend/src/shared/download.js
function downloadQuizHTML() {
  const questions = state.quiz.questions.filter(
    (_, index) => !state.removedQuestions?.has(index)
  );
  const appData2 = {
    mode: state.mode,
    enableMathJax: state.mathReady,
    quiz: { ...state.quiz, questions },
    // srs appdata
    srsOnLoad: state.srs,
    srsQueueSize: state.srsQueueSize,
    requestRetention: state.srsConfig.request_retention,
    srsConfig: state.srsConfig
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
  const ratingIndicator = documentClone.querySelector("#rating-indicator");
  if (ratingIndicator) {
    ratingIndicator.replaceChildren();
    ratingIndicator.className = "";
  }
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
  await copyToClipboard(
    formatQuiz({ title: state.quiz.title, questions: [question] })
  );
}
async function copyQuiz() {
  await copyToClipboard(formatQuiz(orderedQuiz()));
}
async function copyQuizAsFlashcards() {
  await copyToClipboard(formatQuizAsFlashcards(orderedQuiz()));
}
function orderedQuiz() {
  return {
    ...state.quiz,
    questions: state.questionOrder.map(
      (questionIndex) => state.quiz.questions[questionIndex]
    )
  };
}
function formatQuiz(quiz2) {
  if (quiz2.questions.every(isSingleChoice)) {
    return formatQuizAsFlashcards(quiz2);
  }
  return formatQuizAsText({
    ...quiz2,
    questions: normalizeSingleChoiceQuestions(quiz2.questions)
  });
}
function isSingleChoice(question) {
  return question.options.length === 1;
}
function normalizeSingleChoiceQuestions(questions) {
  return questions.map(
    (question) => isSingleChoice(question) ? {
      ...question,
      options: [...question.options, "N/A"]
    } : question
  );
}
async function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.warn("Clipboard API failed, trying fallback:", error);
    }
  }
  return copyToClipboardFallback(text);
}
function copyToClipboardFallback(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  textarea.setAttribute("readonly", "");
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  let success = false;
  try {
    success = document.execCommand("copy");
  } catch (error) {
    console.error("Fallback copy failed:", error);
  }
  document.body.removeChild(textarea);
  return success;
}

// frontend/src/rendering/order.js
var workingOrder = null;
var originalOrder = null;
var dragIndex = null;
var keyHandler = null;
var sessionAddedIndexes = [];
var draggedItems = /* @__PURE__ */ new Set();
var dragCancel = null;
var mouseDragScroll = null;
var mouseDragY = null;
var lastPointerType = "mouse";
document.addEventListener(
  "pointerdown",
  (event) => {
    lastPointerType = event.pointerType;
  },
  true
);
document.addEventListener(
  "dragover",
  (event) => {
    if (mouseDragScroll === null) {
      return;
    }
    event.preventDefault();
    mouseDragY = event.clientY;
    mouseDragScroll.track(mouseDragY);
    highlightSlotUnderPointer(mouseDragY);
  },
  true
);
document.addEventListener(
  "drop",
  (event) => {
    if (mouseDragScroll === null) {
      return;
    }
    event.preventDefault();
    dropMouseDrag(event.clientY ?? mouseDragY);
  },
  true
);
document.addEventListener(
  "dragend",
  () => {
    if (mouseDragScroll !== null) {
      stopMouseDrag();
    }
  },
  true
);
function getQuestionSnippet(questionIndex) {
  const question = state.quiz.questions[questionIndex];
  if (!question) {
    return "(empty question)";
  }
  const scratch = document.createElement("div");
  scratch.innerHTML = question.question || "";
  const text = scratch.textContent.trim();
  if (text === "") {
    return "(empty question)";
  }
  return text.length > 60 ? `${text.slice(0, 60)}\u2026` : text;
}
function openOrderEditor() {
  dragCancel?.();
  stopMouseDrag();
  originalOrder = state.questionOrder.slice();
  workingOrder = state.questionOrder.slice();
  sessionAddedIndexes = [];
  draggedItems.clear();
  document.getElementById("order-editor").classList.remove("dragging");
  buildOrderList();
  keyHandler = (e) => {
    if (e.key !== "Escape") {
      return;
    }
    if (document.getElementById("global-prompt").classList.contains("visible")) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    cancelOrderEditor();
  };
  document.addEventListener("keydown", keyHandler, true);
  document.getElementById("order-editor").classList.add("visible");
  queryRow(state.currentQuestionIndex)?.scrollIntoView({ block: "nearest" });
}
function queryRow(questionIndex) {
  return document.getElementById("order-editor-list").querySelector(`.order-row[data-question-index="${questionIndex}"]`);
}
function selectQuestion(questionIndex) {
  if (questionIndex === state.currentQuestionIndex) {
    return;
  }
  const switchQuestion = () => {
    state.currentQuestionIndex = questionIndex;
    goTo(questionIndex);
    openEditor();
    buildOrderList();
  };
  if (!hasUnsavedEditorChanges()) {
    switchQuestion();
    return;
  }
  showPrompt(
    `Switch to question ${state.questionOrder.indexOf(questionIndex) + 1}?
Unsaved changes to the current question will be lost.`,
    switchQuestion,
    null,
    "yes",
    "no"
  );
}
function closeOrderEditor() {
  dragCancel?.();
  stopMouseDrag();
  sessionAddedIndexes = [];
  document.getElementById("order-editor").classList.remove("visible");
  document.removeEventListener("keydown", keyHandler, true);
  keyHandler = null;
}
function cancelOrderEditor() {
  if (sessionAddedIndexes.length === 0) {
    closeOrderEditor();
    return;
  }
  const added = sessionAddedIndexes.length;
  showPrompt(
    added === 1 ? "Cancel? The question you added will be removed again." : `Cancel? The ${added} questions you added will be removed again.`,
    () => {
      rollBackAddedQuestions();
      closeOrderEditor();
    },
    null,
    "yes",
    "no"
  );
}
function rollBackAddedQuestions() {
  const editedWasAdded = sessionAddedIndexes.includes(
    state.currentQuestionIndex
  );
  for (const index of [...sessionAddedIndexes].sort((a, b) => b - a)) {
    removeAddedQuestion(index);
  }
  sessionAddedIndexes = [];
  originalOrder = state.questionOrder.slice();
  workingOrder = state.questionOrder.slice();
  if (editedWasAdded) {
    state.currentQuestionIndex = state.quiz.questions.length - 1;
    goTo(state.currentQuestionIndex);
    openEditor();
    return;
  }
  updateEditorQuestionNumber();
}
function addOrderQuestion(where = "end") {
  const savedPosition = state.questionOrder.indexOf(state.currentQuestionIndex);
  const listPosition = workingOrder.indexOf(state.currentQuestionIndex);
  let orderPosition = null;
  if (where !== "end" && savedPosition !== -1) {
    orderPosition = where === "before" ? savedPosition : savedPosition + 1;
  }
  const index = addQuestion(orderPosition);
  sessionAddedIndexes.push(index);
  let stagedPosition = workingOrder.length;
  if (where !== "end" && listPosition !== -1) {
    stagedPosition = where === "before" ? listPosition : listPosition + 1;
  }
  workingOrder.splice(stagedPosition, 0, index);
  originalOrder.splice(stagedPosition, 0, index);
  buildOrderList();
  queryRow(index)?.scrollIntoView({ block: "nearest" });
  updateEditorQuestionNumber();
}
function deleteCurrentQuestion() {
  const index = state.currentQuestionIndex;
  const position = Math.max(0, workingOrder.indexOf(index));
  if (state.questionOrder.length <= 1) {
    showAlert("A quiz needs at least one question.");
    return;
  }
  showPrompt(
    "Delete the current question?\nIt will be removed from the quiz.",
    () => {
      const shifted = index >= state.builtInQuestionCount;
      deleteQuestion(index);
      dropFromStagedOrders(index, shifted);
      const nextIndex = workingOrder[Math.min(position, workingOrder.length - 1)];
      state.currentQuestionIndex = nextIndex;
      goTo(nextIndex);
      openEditor();
      buildOrderList();
    },
    null,
    "yes",
    "no"
  );
}
function dropFromStagedOrders(index, shifted) {
  const drop = (order) => order.filter((item) => item !== index).map((item) => shifted && item > index ? item - 1 : item);
  workingOrder = drop(workingOrder);
  originalOrder = drop(originalOrder);
}
function saveOrder() {
  if (JSON.stringify(workingOrder) !== JSON.stringify(originalOrder)) {
    state.questionOrder = workingOrder.slice();
    saveQuestionOrder(state.quizStorageKey, state.questionOrder);
    updateQuestionNumbers();
    updateQuestionCounts();
    updateEditorQuestionNumber();
  }
  closeOrderEditor();
}
function startGripDrag(event, position) {
  dragCancel?.();
  const list = document.getElementById("order-editor-list");
  const overlay = document.getElementById("order-editor");
  const pointerId = event.pointerId;
  const row = list.querySelectorAll(".order-row")[position];
  let done = false;
  const scroll = createDragAutoScroll(handlePointerDragOver);
  const cleanup = () => {
    if (done) {
      return;
    }
    done = true;
    scroll.stop();
    overlay.classList.remove("dragging");
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    document.removeEventListener("pointercancel", onUp);
    document.removeEventListener("pointerdown", onOtherPointer, true);
    if (row) {
      row.classList.remove("order-dragging");
    }
    dragIndex = null;
    if (dragCancel === cleanup) {
      dragCancel = null;
    }
  };
  const onMove = (moveEvent) => {
    if (moveEvent.pointerId !== pointerId) {
      return;
    }
    moveEvent.preventDefault();
    scroll.track(moveEvent.clientY);
    handlePointerDragOver(moveEvent.clientY);
  };
  const onUp = (upEvent) => {
    if (upEvent.pointerId === pointerId) {
      cleanup();
    }
  };
  const onOtherPointer = (downEvent) => {
    if (!downEvent.isPrimary) {
      cleanup();
    }
  };
  dragIndex = position;
  dragCancel = cleanup;
  overlay.classList.add("dragging");
  if (row) {
    row.classList.add("order-dragging");
  }
  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
  document.addEventListener("pointercancel", onUp);
  document.addEventListener("pointerdown", onOtherPointer, true);
}
function startMouseDrag(event, position, row) {
  stopMouseDrag();
  dragIndex = position;
  mouseDragY = event.clientY;
  row?.classList.add("order-dragging");
  mouseDragScroll = createDragAutoScroll(highlightSlotUnderPointer);
  mouseDragScroll.track(mouseDragY);
}
function stopMouseDrag() {
  mouseDragScroll?.stop();
  mouseDragScroll = null;
  mouseDragY = null;
  dragIndex = null;
  document.querySelectorAll(
    "#order-editor-list .order-dragging, #order-editor-list .order-drop-target"
  ).forEach((row) => {
    row.classList.remove("order-dragging", "order-drop-target");
  });
}
function dropMouseDrag(pointerY) {
  const from = dragIndex;
  const { rows, target } = slotUnderPointer(pointerY);
  stopMouseDrag();
  if (from === null || rows.length === 0 || from === target) {
    return;
  }
  const [item] = workingOrder.splice(from, 1);
  workingOrder.splice(target, 0, item);
  draggedItems.add(item);
  buildOrderList();
}
function handlePointerDragOver(pointerY) {
  const list = document.getElementById("order-editor-list");
  const dragged = list.querySelector(".order-row.order-dragging");
  if (!dragged) {
    return;
  }
  const { rows, target } = slotUnderPointer(pointerY);
  const from = rows.indexOf(dragged);
  if (target === from) {
    return;
  }
  const reference = target > from ? rows[target].nextSibling : rows[target];
  list.insertBefore(dragged, reference);
  const [item] = workingOrder.splice(from, 1);
  workingOrder.splice(target, 0, item);
  draggedItems.add(Number(dragged.dataset.questionIndex));
  updateRowLabels();
}
function slotUnderPointer(pointerY) {
  const list = document.getElementById("order-editor-list");
  const rows = Array.from(list.querySelectorAll(".order-row"));
  let target = rows.length - 1;
  for (let index = 0; index < rows.length; index++) {
    const rect = rows[index].getBoundingClientRect();
    if (pointerY < rect.top + rect.height / 2) {
      target = index;
      break;
    }
  }
  return { rows, target };
}
function highlightSlotUnderPointer(pointerY) {
  const { rows, target } = slotUnderPointer(pointerY);
  rows.forEach((row, index) => {
    row.classList.toggle(
      "order-drop-target",
      index === target && !row.classList.contains("order-dragging")
    );
  });
}
function createDragAutoScroll(onScroll) {
  let frame = null;
  let pointerY = null;
  const step = () => {
    frame = null;
    if (pointerY === null || scrollListOutsidePointer(pointerY) === 0) {
      return;
    }
    onScroll?.(pointerY);
    frame = requestAnimationFrame(step);
  };
  return {
    track(position) {
      pointerY = position;
      if (frame === null) {
        frame = requestAnimationFrame(step);
      }
    },
    stop() {
      if (frame !== null) {
        cancelAnimationFrame(frame);
      }
      frame = null;
      pointerY = null;
    }
  };
}
function scrollListOutsidePointer(pointerY) {
  const list = document.getElementById("order-editor-list");
  const rect = list.getBoundingClientRect();
  let distance = 0;
  let direction = 0;
  if (pointerY < rect.top) {
    distance = rect.top - pointerY;
    direction = -1;
  } else if (pointerY > rect.bottom) {
    distance = pointerY - rect.bottom;
    direction = 1;
  } else {
    return 0;
  }
  const cap = Math.max(40, list.scrollHeight / 40);
  const speed = Math.min(cap, 2 + distance / 4 + distance * distance / 700);
  const step = Math.round(speed) * direction;
  const before = list.scrollTop;
  list.scrollTop = before + step;
  return list.scrollTop === before ? 0 : step;
}
function applyRowState(row, position, questionIndex) {
  const changed = originalOrder[position] !== questionIndex;
  const dragged = changed && draggedItems.has(questionIndex);
  row.classList.toggle("order-dragged", dragged);
  row.classList.toggle("order-changed", changed && !dragged);
}
function updateRowLabels() {
  const list = document.getElementById("order-editor-list");
  list.querySelectorAll(".order-row").forEach((row, position) => {
    const number = row.querySelector(".order-number");
    if (number) {
      number.textContent = `${position + 1}.`;
    }
    applyRowState(row, position, Number(row.dataset.questionIndex));
  });
}
function buildOrderList() {
  const list = document.getElementById("order-editor-list");
  list.replaceChildren();
  workingOrder.forEach((questionIndex, position) => {
    const row = document.createElement("div");
    row.className = "order-row";
    row.draggable = true;
    applyRowState(row, position, questionIndex);
    if (questionIndex === state.currentQuestionIndex) {
      row.classList.add("order-current");
      row.setAttribute("aria-current", "true");
    }
    const number = document.createElement("span");
    number.className = "order-number";
    number.textContent = `${position + 1}.`;
    const caption = document.createElement("span");
    caption.className = "order-caption";
    caption.textContent = getQuestionSnippet(questionIndex);
    row.dataset.questionIndex = String(questionIndex);
    const currentPosition = () => workingOrder.indexOf(Number(row.dataset.questionIndex));
    const handle = document.createElement("span");
    handle.className = "order-handle";
    handle.textContent = "\u283F";
    handle.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse") {
        return;
      }
      if (!event.isPrimary) {
        return;
      }
      startGripDrag(event, currentPosition());
    });
    handle.addEventListener(
      "touchstart",
      (event) => {
        if (event.touches.length === 1) {
          event.preventDefault();
        }
      },
      { passive: false }
    );
    row.appendChild(handle);
    row.appendChild(number);
    row.appendChild(caption);
    row.addEventListener("dragstart", (event) => {
      if (lastPointerType !== "mouse") {
        event.preventDefault();
        return;
      }
      startMouseDrag(event, currentPosition(), row);
    });
    row.addEventListener("click", () => selectQuestion(questionIndex));
    list.appendChild(row);
  });
}
document.getElementById("order-editor-save").addEventListener("click", saveOrder);
document.getElementById("order-editor-cancel").addEventListener("click", cancelOrderEditor);
document.getElementById("order-editor-add").addEventListener("click", () => addOrderQuestion("end"));
document.getElementById("order-editor-add-before").addEventListener("click", () => addOrderQuestion("before"));
document.getElementById("order-editor-add-after").addEventListener("click", () => addOrderQuestion("after"));
document.getElementById("order-editor-delete").addEventListener("click", deleteCurrentQuestion);

// frontend/src/rendering/editor.js
document.getElementById("editor-answer-number").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/\D/g, "");
});
function updateEditorQuestionNumber() {
  const orderIndex = state.questionOrder.indexOf(state.currentQuestionIndex);
  const questionPosition = orderIndex === -1 ? state.currentQuestionIndex + 1 : orderIndex + 1;
  document.getElementById("editor-question-number").textContent = `Question ${questionPosition} of ${state.questionOrder.length}`;
}
function openEditor() {
  const editor = document.getElementById("editor");
  document.getElementById("flashcard-box").style.display = "none";
  document.getElementById("question-box").style.display = "none";
  editor.style.display = "";
  const titleField = document.getElementById("editor-title");
  const questionField = document.getElementById("editor-question");
  const explanationField = document.getElementById("editor-explanation");
  const editorAnswer = document.getElementById("editor-answer-number");
  const optionsContainer = document.getElementById("editor-distractors");
  const question = state.quiz.questions[state.currentQuestionIndex];
  updateEditorQuestionNumber();
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
  loadAdditionalSettings();
  rememberEditorValues();
}
var additionalSettingsSnapshot = null;
function getEditorSettingsValues() {
  const edit = (id) => document.getElementById(id);
  return {
    srsQueueSize: parseInt(edit("editor-srs-queue-size").value, 10),
    srsConfig: {
      request_retention: parseFloat(
        edit("editor-fsrs-request-retention").value
      ),
      maximum_interval: parseInt(
        edit("editor-fsrs-maximum-interval").value,
        10
      ),
      enable_fuzz: edit("editor-fsrs-enable-fuzz").checked,
      enable_short_term: edit("editor-fsrs-enable-short-term").checked
    }
  };
}
function loadAdditionalSettings() {
  const config = state.srsConfig;
  document.getElementById("editor-srs-queue-size").value = state.srsQueueSize;
  document.getElementById("editor-fsrs-request-retention").value = config.request_retention;
  document.getElementById("editor-fsrs-maximum-interval").value = config.maximum_interval;
  document.getElementById("editor-fsrs-enable-fuzz").checked = config.enable_fuzz;
  document.getElementById("editor-fsrs-enable-short-term").checked = config.enable_short_term;
  additionalSettingsSnapshot = JSON.stringify(getEditorSettingsValues());
}
var editorSnapshot = null;
function getEditorQuestionValues() {
  const field = (id) => document.querySelector(`#${id} textarea`)?.value ?? "";
  const optionsContainer = document.getElementById("editor-distractors");
  return {
    title: field("editor-title"),
    question: field("editor-question"),
    explanation: field("editor-explanation"),
    answer: document.getElementById("editor-answer-number").value,
    options: Array.from(optionsContainer.querySelectorAll("textarea")).map(
      (textarea) => textarea.value
    )
  };
}
function rememberEditorValues() {
  editorSnapshot = JSON.stringify([
    getEditorQuestionValues(),
    getEditorSettingsValues()
  ]);
}
function hasUnsavedEditorChanges() {
  if (editorSnapshot === null) {
    return false;
  }
  return JSON.stringify([getEditorQuestionValues(), getEditorSettingsValues()]) !== editorSnapshot;
}
document.getElementById("order-editor-open-button").addEventListener("click", openOrderEditor);
function validateAdditionalSettings() {
  const retentionInput = document.getElementById(
    "editor-fsrs-request-retention"
  );
  const intervalInput = document.getElementById("editor-fsrs-maximum-interval");
  const queueInput = document.getElementById("editor-srs-queue-size");
  const retention = parseFloat(retentionInput.value);
  const maximumInterval = parseInt(intervalInput.value, 10);
  const queueSize = parseInt(queueInput.value, 10);
  let valid = true;
  const check = (input, condition) => {
    input.classList.remove("input-error");
    if (!condition) {
      input.classList.add("input-error");
      valid = false;
    }
  };
  check(
    retentionInput,
    !Number.isNaN(retention) && retention > 0 && retention < 1
  );
  check(
    intervalInput,
    Number.isInteger(maximumInterval) && maximumInterval >= 1
  );
  check(queueInput, Number.isInteger(queueSize) && queueSize >= 1);
  if (!valid) {
    showAlert(
      "Invalid Additional Settings: request retention must be between 0 and 1, and the other values must be positive integers."
    );
  }
  return valid;
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
async function saveEdit() {
  if (!validateAnswerIndex() || !validateAdditionalSettings()) {
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
  const settingsChanged = applyAdditionalSettings();
  const questionSaved = saveLocalEdit(state.currentQuestionIndex, titleChanged);
  if (questionSaved || settingsChanged) {
    showAlert("Changes saved.");
  }
  rememberEditorValues();
  if (settingsChanged && state.srs) {
    await initSRS(state.quizStorageKey, state.currentQuestionIndex);
    updateSRSCounts();
  }
}
function applyAdditionalSettings() {
  const values = getEditorSettingsValues();
  const settingsChanged = JSON.stringify(values) !== additionalSettingsSnapshot;
  setSRSConfig(values.srsConfig);
  state.srsQueueSize = values.srsQueueSize;
  if (settingsChanged) {
    saveAppDataOverrides(state.quizStorageKey, {
      srsConfig: { ...state.srsConfig },
      srsQueueSize: state.srsQueueSize
    });
  }
  return settingsChanged;
}
function closeEditor() {
  const editor = document.getElementById("editor");
  editor.style.display = "none";
  const options = document.getElementById("editor-distractors");
  options.innerHTML = "";
  closeOrderEditor();
  goTo(state.currentQuestionIndex);
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
      clearQuestionOrder(state.quizStorageKey);
      clearQuestionRemovals(state.quizStorageKey);
      state.removedQuestions = /* @__PURE__ */ new Set();
      state.questionOrder = loadQuestionOrder(
        state.quizStorageKey,
        state.quiz.questions.length
      );
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
  const appData2 = JSON.parse(document.getElementById("app-data").textContent);
  const index = state.currentQuestionIndex;
  if (index >= appData2.quiz.questions.length) {
    showPrompt(
      "Remove this added question?\nIt will be deleted from the quiz.",
      () => {
        removeAddedQuestion(index);
        state.currentQuestionIndex = Math.min(
          index,
          state.quiz.questions.length - 1
        );
        openEditor();
        showAlert("Added question removed.");
      },
      null,
      "Yes",
      "No"
    );
    return;
  }
  showPrompt(
    "Restore the current question to its original state?\nAll local edits will be discarded.",
    () => {
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
  document.querySelectorAll(".copy-flashcards-button").forEach((button) => {
    button.addEventListener("click", copyQuizAsFlashcards);
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
  document.querySelectorAll(".fsrs-rating-button").forEach((button) => {
    button.addEventListener("click", async () => {
      await rateFSRS(Number(button.dataset.rating));
      nextQuestion();
    });
  });
  document.querySelectorAll(".toggle-srs-button").forEach((button) => {
    button.addEventListener("click", toggleSRS);
  });
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
  document.addEventListener("keydown", async (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (document.getElementById("question-box")?.style.display === "none" && document.getElementById("flashcard-box")?.style.display === "none") {
      return;
    }
    const key = e.key.toLowerCase();
    if (state.answerRevealed && state.srs) {
      if (["1", "2", "3", "4"].includes(key)) {
        await rateFSRS(Number(key));
        nextQuestion();
        return;
      }
    }
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
      } else if (state.srs) {
        await rateFSRS(3);
        nextQuestion();
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
  async function handleBoxClick(e) {
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
        if (state.srs) {
          await rateFSRS(3);
        }
        nextQuestion();
      }
    } else if (x < rect.width * 0.3) {
      if (state.srs) {
        if (state.answerRevealed) {
          await rateFSRS(1);
          nextQuestion();
        }
      } else {
        prevQuestion();
      }
    }
  }
  questionBox.addEventListener("click", handleBoxClick);
  flashcardBox.addEventListener("click", handleBoxClick);
  document.querySelectorAll(".question-selector").forEach((questionSelector) => {
    const questionNumber = questionSelector.querySelector(".question-number");
    questionSelector.addEventListener("click", () => {
      questionNumber.focus();
      questionNumber.select();
    });
    questionNumber.addEventListener("input", () => {
      questionNumber.value = questionNumber.value.replace(/\D/g, "");
    });
    questionNumber.addEventListener("change", () => {
      if (!questionNumber.value) return;
      goToPosition(Number(questionNumber.value));
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
var appData = loadAppData();
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
state.srsQueueSize = appData.srsQueueSize;
Object.assign(state.srsConfig, appData.srsConfig ?? {});
if (appData.srsConfig === void 0) {
  state.srsConfig.request_retention = appData.requestRetention;
}
loadStats();
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
  if (appData.srsOnLoad) {
    await toggleSRS();
  }
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
