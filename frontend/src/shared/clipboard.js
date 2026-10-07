import { state } from "../state.js";
import { formatQuizAsText } from "./formatting.js";

export async function copyQuestion() {
  const question = state.quiz.questions[state.currentQuestionIndex];

  const quiz = {
    title: state.quiz.title,
    questions: normalizeSingleChoiceQuestions([question]),
  };

  await copyToClipboard(formatQuizAsText(quiz));
}

/**
 * Copies the quiz using state.questionOrder as the question order.
 *
 * @returns {Promise<void>}
 */
export async function copyQuiz() {
  const quiz = {
    ...state.quiz,
    questions: normalizeSingleChoiceQuestions(
      state.questionOrder.map(
        (questionIndex) => state.quiz.questions[questionIndex],
      ),
    ),
  };

  await copyToClipboard(formatQuizAsText(quiz));
}

/**
 * Adds a second option to questions with only one choice so that the
 * text representation remains parseable.
 *
 * @param {Array<{ options: string[] }>} questions
 * @returns {Array<{ options: string[] }>}
 */
function normalizeSingleChoiceQuestions(questions) {
  return questions.map((question) =>
    question.options.length === 1
      ? {
          ...question,
          options: [...question.options, "N/A"],
        }
      : question,
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
