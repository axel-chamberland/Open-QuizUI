"""
title: QuizUI
author: Axel Chamberland
git_url: https://github.com/axel-chamberland/OpenQuizUI
description: Converts a multiple choice quiz messages into an interactive HTML quiz
version: 1.0
"""

from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse
import re
import json
import random


class Action:
    class Valves(BaseModel):
        # TODO: Add variants: option as numbers instead of letters. Questions as letters instead of options

        # TODO: Option to define a custom format?

        # TODO: Option to show explanation? Would be hard to implement

        shuffle_choices: bool = Field(
            default=True,
            description="Shuffle the order of choices",
        )
        enable_mathjax: bool = Field(
            default=False,
            description="Disabled by default for privacy and performance. Enable LaTeX/math rendering with MathJax. Requires Internet access to load the MathJax library from a CDN. When disabled or offline, LaTeX expressions are displayed as plain text.",
        )
        question_format: str = Field(
            default="standard",
            description="Format of the questions. Options: 'standard' (flexible detection)",
        )
        answer_format: str = Field(
            default="standard",
            description="How the answer key is presented. Options: 'standard' (A header followed by a numbered list of correct answers with a,b,c,d,...)",
        )
        # TODO: implement this
        dark_mode: int = Field(
            default=-1,
            description="-1: Let browser decide. 0: Light mode. 1: Enable dark mode",
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
            # for k, v in body["messages"][0].items():
            #     prints.append((k, type(v)))
            # raise Exception(f"{prints}")

            text = body["messages"][-1]["content"]

            # Remove HTML tags, reasoning blocks and other artifacts
            text = clean_text(text)

            if not text:
                raise ValueError("No quiz content received")

            title, questions = parse_quiz(text)

            if self.valves.shuffle_choices:
                shuffle_options(questions)

            quiz = {"title": title, "questions": questions}

            content = wrap_html(quiz, self.valves.enable_mathjax)

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
        r"^\s*\*{0,2}\d+\s*\*{0,2}\s*[\.\):-]\s*\*{0,2}([A-Z])\*{0,2}\b",
        # Réponse : B / Answer: B / Correct answer: B or even **Answer** or **R:** or R:
        r"^\s*\*{0,2}(?:réponse|answer|correct answer|r|a)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*([A-Z])\b",
        # In Bullet Point
        r"^\s*[*\-]?\s*\*{0,2}\s*(?:r|answer|réponse|correct answer)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*([A-Z])\b",
        # **Q1 Answer:** **c) ...** / **Q1 Answer:** **c)** trailing text
        r"^\s*\*{0,2}\s*q\s*\d+\s*(?:r|answer|réponse|correct answer)\s*\*{0,2}\s*[:\-]?\s*\*{0,2}\s*\*{0,2}\s*([A-Z])\b",
        # Question 1 : B
        r"^\s*question\s*\d+.*?([A-Z])\b",
    ]

    for pattern in answer_patterns:
        matches = [m.group(1).upper() for m in re.finditer(pattern, text, re.I | re.M)]

        if len(matches) == len(questions):  # Verification step
            for q, letter in zip(questions, matches):
                q["correct_index"] = ord(letter) - ord("A")
            break
    else:
        raise ValueError("Failed to parse answers")

    return title, questions


def question_parser_standard(lines):
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
        r"(?:#{1,6}\s*)?"  # Optional Markdown Header (#) or bold (**)
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

    def is_tag_like(s):
        return bool(re.fullmatch(r"[<\[].*[>\]]", s))

    scored = []  # (score, title_text)
    for line in candidates:
        s = line.strip()
        if not s or is_tag_like(s):
            continue

        heading_match = re.match(r"^#{1,6}\s*(.+)$", s)
        if heading_match:
            heading_text = heading_match.group(1).strip(" *_")
            if heading_text and "question" not in heading_text.lower():
                scored.append((3, heading_text))
                continue

        quote_match = re.search(r'["“]([^"”]{6,80})["”]', s)
        if quote_match:
            quoted = quote_match.group(1).strip(" *_")
            if "question" not in quoted.lower():
                scored.append((2, quoted))
                continue

        bold_match = re.fullmatch(r"\*\*(.+)\*\*[:.]?", s)
        if bold_match:
            bold_text = bold_match.group(1).strip(" *_")
            if bold_text and len(bold_text) > 5 and "question" not in bold_text.lower():
                scored.append((2, bold_text))
                continue

        clean = re.sub(r"[#*_`>-]", "", s).strip()
        if clean and len(clean) > 5 and "question" not in clean.lower():
            scored.append((1, clean))

    if not scored:
        return "Quiz"

    best_score = max(s[0] for s in scored)
    best = [c for c in scored if c[0] == best_score]
    return best[-1][1]


# =========================================================
# HELPERS
# =========================================================


def clean_text(text: str):
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


def wrap_html(quiz, enable_mathjax: bool):
    quiz_json = json.dumps(quiz)

    global script
    script = script.replace("__ENABLE_MATHJAX__", "true" if enable_mathjax else "false")

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Quiz</title>

<style>
{style}
</style>
</head>

<body>
<div class="question-box">
  <h1></h1>
  <p id="question"></p>
  <div id="options"></div>

  <div id="navigation">
    <button id="prevButton">Previous</button>
    <button id="revealButton">Reveal</button>
    <button id="nextButton">Next</button>
  </div>
</div>

<script>
const quiz = {quiz_json};
{script}
</script>

</body>
</html>
"""


# =========================
# STYLE
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

style = """
:root {
    color-scheme: light dark;

    --bg: oklch(100% 0 0);
    --btn: oklch(94% 0 0);
    --text: oklch(20% 0 0);
    --border: oklch(85% 0 0);

    --surface: color-mix(in srgb, var(--bg) 92%, var(--text) 8%);
    --surface-2: color-mix(in srgb, var(--bg) 96%, var(--text) 4%);

    --success: #00c853;
    --danger: #dc3545;
}

@media (prefers-color-scheme: dark) {
    :root {
        --bg: oklch(20% 0 0);
        --btn: oklch(20% 0 0);
        --text: oklch(94% 0 0);
        --border: oklch(85% 0 0);

        --surface: color-mix(in srgb, var(--bg) 92%, var(--text) 8%);
        --surface-2: color-mix(in srgb, var(--bg) 85%, var(--bg) 15%);
    }
}


body {
    margin: 0;
    padding: 0;
    background: var(--bg);
}

.question-box {
    padding: 2rem;
    background: var(--bg);
    color: var(--text);
}

#question {
    margin-bottom: 2em;
    font-size: 1.1rem;
}

#options {-webkit-appearance: none;
    display: grid;
    gap: 0.75rem;
    margin-bottom: 2em;
    padding: 0 1.5rem;
}

.option {
    padding: 1rem;
    font-size: 1.1rem;
    border: 1px solid;
    border-color: var(--border);
    border-radius: 0.25rem;
    background: var(--btn);
    cursor: pointer;
    text-align: center;
    color: var(--text)
}

.option:hover {
    filter: brightness(1.5);
}

.option.correct {
    background: color-mix(in srgb, var(--success) 30%, var(--surface));
    border-color: var(--success);
}

.option.wrong {
    background: color-mix(in srgb, var(--danger) 30%, var(--surface));
    border-color: var(--danger);
}

#navigation {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 2rem;
}

"""


# =========================
# SCRIPT (Front End)
# =========================

script = r"""
// Try to load math library (WARNING: requires internet)
const ENABLE_MATHJAX = __ENABLE_MATHJAX__;

let mathReady = false;

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

// Helpers

function typesetMath() {
  if (window.MathJax) {
    MathJax.typesetPromise?.();
  }
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
function renderMath(text) {
  if (!text) return "";

  return text.replace(/\$(.+?)\$/g, (match, expr) => {
    if (mathReady && window.MathJax) {
      return match;
    }
    return `<code>${expr}</code>`;
  });
}

function simpleMarkdownInline(text) {
  if (!text) return "";

  return renderMath(
    escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
      .replace(/\*(.*?)\*/g, "<i>$1</i>")
  );
}

function simpleMarkdownBlock(text) {
  if (!text) return "";
  return simpleMarkdownInline(text).replace(/\n/g, "<br>");
}


// Height reporting script
function reportHeight() {
  const h = document.documentElement.scrollHeight;
  parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
new ResizeObserver(reportHeight).observe(document.body);

let currentQuestionIndex = 0;
let wrongAnswerCount = 0;

function renderQuiz() {
  const questionBox = document.querySelector(".question-box");
  const questionBoxTitle = questionBox.querySelector("h1");
  const questionText = questionBox.querySelector("#question");
  const optionsContainer = document.getElementById("options");
  const navigationContainer = questionBox.querySelector("#navigation");

  if (!quiz.questions || quiz.questions.length === 0) {
    document.getElementById("question").textContent = "No valid questions parsed";
    return;
  }
  
  // Update question
  questionBoxTitle.textContent = `${quiz.title} (${currentQuestionIndex + 1}/${quiz.questions.length})`;
  questionText.innerHTML = simpleMarkdownBlock(quiz.questions[currentQuestionIndex].question);

  // Clear and rebuild options
  optionsContainer.innerHTML = '';
  wrongAnswerCount = 0; // Answer button is revealed when user exhausted all options

  const currentQuestion = quiz.questions[currentQuestionIndex];

  currentQuestion.options.forEach((option, index) => {
    const button = document.createElement("button");
    button.innerHTML = simpleMarkdownInline(option);
    button.className = 'option'

    button.addEventListener("click", () => {
      if (index === currentQuestion.correct_index) {
        button.classList.add('correct');
        button.disabled = true;
        const allButtons = document.querySelectorAll('.option');
        allButtons.forEach(btn => btn.disabled = true);
      } else {
        button.classList.add('wrong');
        button.disabled = true;
        wrongAnswerCount++;
        const totalOptions = currentQuestion.options.length;
        if (wrongAnswerCount === totalOptions - 1) {
          revealAnswer();
          button.disabled = true;
        }
      }
    });

    optionsContainer.appendChild(button);

  });

  // Update button states
  const prevButton = navigationContainer.querySelector("#prevButton");
  const nextButton = navigationContainer.querySelector("#nextButton");

  prevButton.disabled = currentQuestionIndex === 0;
  nextButton.disabled = currentQuestionIndex === quiz.questions.length - 1;

if (window.MathJax) {
  setTimeout(() => {
    MathJax.typesetPromise?.();
  }, 0);
}
}

function nextQuestion() {
  if (currentQuestionIndex + 1 < quiz.questions.length) {
    currentQuestionIndex++
    renderQuiz();
  } else {
    renderQuiz();
  }
}

function revealAnswer() {
  const currentQuestion = quiz.questions[currentQuestionIndex];
  const optionsContainer = document.getElementById("options");

  // Get all buttons in the current question
  const buttons = optionsContainer.querySelectorAll("button");

  // Find and highlight the correct answer
  buttons.forEach(button => {
    const buttonIndex = Array.from(buttons).indexOf(button);
    if (buttonIndex === currentQuestion.correct_index) {
      button.classList.add('correct');
    }
  });
}

// Handle navigation buttons
const nextButton = document.getElementById("nextButton");
nextButton.addEventListener("click", nextQuestion);

const prevButton = document.getElementById("prevButton");
prevButton.addEventListener("click", () => {
  currentQuestionIndex = Math.max(0, currentQuestionIndex - 1);
  renderQuiz();
});

const revealButton = document.getElementById("revealButton");
revealButton.addEventListener("click", revealAnswer);

loadMathJax().then(() => {
  if (window.MathJax?.startup?.promise) {
    MathJax.startup.promise.then(renderQuiz);
  } else {
    renderQuiz();
  }
});
"""
